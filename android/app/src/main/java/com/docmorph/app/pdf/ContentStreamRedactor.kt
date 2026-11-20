package com.docmorph.app.pdf

import com.tom_roush.pdfbox.contentstream.operator.Operator
import com.tom_roush.pdfbox.cos.COSArray
import com.tom_roush.pdfbox.cos.COSBase
import com.tom_roush.pdfbox.cos.COSFloat
import com.tom_roush.pdfbox.cos.COSInteger
import com.tom_roush.pdfbox.cos.COSName
import com.tom_roush.pdfbox.cos.COSNumber
import com.tom_roush.pdfbox.cos.COSString
import com.tom_roush.pdfbox.pdfparser.PDFStreamParser
import com.tom_roush.pdfbox.pdfwriter.ContentStreamWriter
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.pdmodel.PDPage
import com.tom_roush.pdfbox.pdmodel.common.PDStream
import com.tom_roush.pdfbox.pdmodel.graphics.form.PDFormXObject
import com.tom_roush.pdfbox.util.Matrix
import java.util.ArrayDeque
import kotlin.math.max
import kotlin.math.min

data class RedactionTarget(
    val originalText: String,
    val rawBbox: List<Float>, // [x0, y0, x1, y1] in top-down PDF points
    val pageIndex: Int
)

class ContentStreamRedactor {

    /**
     * Rewrites the page content stream to remove text-showing operators intersecting
     * the target redaction regions, preserving all vector lines, borders, and images.
     * Also recursively inspects and redacts within Form XObjects (e.g. repeated footers).
     */
    fun redactPage(document: PDDocument, page: PDPage, targets: List<RedactionTarget>): Int {
        if (targets.isEmpty()) return 0

        val cropBox = page.cropBox ?: page.mediaBox
        val pageHeight = cropBox.height
        val originX = cropBox.lowerLeftX
        val originY = cropBox.lowerLeftY

        // Convert targets to user space (bottom-up coordinates)
        val userTargets = targets.map { target ->
            val x0 = target.rawBbox[0]
            val y0 = target.rawBbox[1]
            val x1 = target.rawBbox[2]
            val y1 = target.rawBbox[3]

            UserTarget(
                originalText = target.originalText.trim(),
                pdfX0 = originX + x0 - 4.0f,
                pdfX1 = originX + x1 + 4.0f,
                pdfY0 = originY + (pageHeight - y1) - 4.0f,
                pdfY1 = originY + (pageHeight - y0) + 4.0f
            )
        }

        var totalPurged = 0

        // 1. Redact direct page content stream
        val parser: PDFStreamParser
        try {
            parser = PDFStreamParser(page)
            parser.parse()
            val tokens = parser.tokens
            if (tokens.isNotEmpty()) {
                val (newTokens, purged) = redactTokenStream(page, tokens, userTargets)
                if (purged > 0) {
                    val newStream = PDStream(document)
                    val out = newStream.createOutputStream(COSName.FLATE_DECODE)
                    val writer = ContentStreamWriter(out)
                    writer.writeTokens(newTokens)
                    out.close()
                    page.setContents(newStream)
                    totalPurged += purged
                }
            }
        } catch (_: Exception) {}

        // 2. Redact text within Form XObjects referenced by this page (repeated footers/headers)
        try {
            val resources = page.resources
            if (resources != null) {
                for (name in resources.xObjectNames) {
                    try {
                        val xobj = resources.getXObject(name)
                        if (xobj is PDFormXObject) {
                            val formParser = PDFStreamParser(xobj)
                            formParser.parse()
                            val formTokens = formParser.tokens
                            if (formTokens.isNotEmpty()) {
                                val (newFormTokens, formPurged) = redactTokenStream(page, formTokens, userTargets)
                                if (formPurged > 0) {
                                    val out = xobj.cosObject.createOutputStream(COSName.FLATE_DECODE)
                                    val writer = ContentStreamWriter(out)
                                    writer.writeTokens(newFormTokens)
                                    out.close()
                                    totalPurged += formPurged
                                }
                            }
                        }
                    } catch (_: Exception) {}
                }
            }
        } catch (_: Exception) {}

        return totalPurged
    }

    private data class UserTarget(
        val originalText: String,
        val pdfX0: Float,
        val pdfX1: Float,
        val pdfY0: Float,
        val pdfY1: Float
    )

    private fun redactTokenStream(
        page: PDPage,
        tokens: List<Any>,
        userTargets: List<UserTarget>
    ): Pair<List<Any>, Int> {
        val newTokens = mutableListOf<Any>()
        val currentArgs = mutableListOf<COSBase>()

        val ctmStack = ArrayDeque<Matrix>()
        var ctm = Matrix()
        var textMatrix = Matrix()
        var textLineMatrix = Matrix()
        var textLeading = 0f
        var currentFontName: String? = null
        var currentFontSize = 10f

        var purgedCount = 0

        for (token in tokens) {
            if (token is COSBase) {
                currentArgs.add(token)
                continue
            }

            if (token is Operator) {
                val opName = token.name

                when (opName) {
                    "q" -> {
                        ctmStack.push(ctm.clone())
                        newTokens.addAll(currentArgs)
                        newTokens.add(token)
                        currentArgs.clear()
                    }
                    "Q" -> {
                        if (ctmStack.isNotEmpty()) {
                            ctm = ctmStack.pop()
                        }
                        newTokens.addAll(currentArgs)
                        newTokens.add(token)
                        currentArgs.clear()
                    }
                    "cm" -> {
                        if (currentArgs.size >= 6) {
                            val a = getFloat(currentArgs[0])
                            val b = getFloat(currentArgs[1])
                            val c = getFloat(currentArgs[2])
                            val d = getFloat(currentArgs[3])
                            val e = getFloat(currentArgs[4])
                            val f = getFloat(currentArgs[5])
                            val cmMatrix = Matrix(a, b, c, d, e, f)
                            ctm = cmMatrix.multiply(ctm)
                        }
                        newTokens.addAll(currentArgs)
                        newTokens.add(token)
                        currentArgs.clear()
                    }
                    "BT" -> {
                        textMatrix = Matrix()
                        textLineMatrix = Matrix()
                        newTokens.addAll(currentArgs)
                        newTokens.add(token)
                        currentArgs.clear()
                    }
                    "ET" -> {
                        newTokens.addAll(currentArgs)
                        newTokens.add(token)
                        currentArgs.clear()
                    }
                    "Tf" -> {
                        if (currentArgs.size >= 2) {
                            val fontArg = currentArgs[0]
                            if (fontArg is COSName) {
                                currentFontName = fontArg.name
                            }
                            currentFontSize = getFloat(currentArgs[1])
                        }
                        newTokens.addAll(currentArgs)
                        newTokens.add(token)
                        currentArgs.clear()
                    }
                    "Tm" -> {
                        if (currentArgs.size >= 6) {
                            val a = getFloat(currentArgs[0])
                            val b = getFloat(currentArgs[1])
                            val c = getFloat(currentArgs[2])
                            val d = getFloat(currentArgs[3])
                            val e = getFloat(currentArgs[4])
                            val f = getFloat(currentArgs[5])
                            textMatrix = Matrix(a, b, c, d, e, f)
                            textLineMatrix = textMatrix.clone()
                        }
                        newTokens.addAll(currentArgs)
                        newTokens.add(token)
                        currentArgs.clear()
                    }
                    "Td" -> {
                        if (currentArgs.size >= 2) {
                            val tx = getFloat(currentArgs[0])
                            val ty = getFloat(currentArgs[1])
                            val tdMatrix = Matrix.getTranslateInstance(tx, ty)
                            textLineMatrix = tdMatrix.multiply(textLineMatrix)
                            textMatrix = textLineMatrix.clone()
                        }
                        newTokens.addAll(currentArgs)
                        newTokens.add(token)
                        currentArgs.clear()
                    }
                    "TD" -> {
                        if (currentArgs.size >= 2) {
                            val tx = getFloat(currentArgs[0])
                            val ty = getFloat(currentArgs[1])
                            textLeading = -ty
                            val tdMatrix = Matrix.getTranslateInstance(tx, ty)
                            textLineMatrix = tdMatrix.multiply(textLineMatrix)
                            textMatrix = textLineMatrix.clone()
                        }
                        newTokens.addAll(currentArgs)
                        newTokens.add(token)
                        currentArgs.clear()
                    }
                    "T*" -> {
                        val tdMatrix = Matrix.getTranslateInstance(0f, -textLeading)
                        textLineMatrix = tdMatrix.multiply(textLineMatrix)
                        textMatrix = textLineMatrix.clone()
                        newTokens.addAll(currentArgs)
                        newTokens.add(token)
                        currentArgs.clear()
                    }
                    "TL" -> {
                        if (currentArgs.isNotEmpty()) {
                            textLeading = getFloat(currentArgs[0])
                        }
                        newTokens.addAll(currentArgs)
                        newTokens.add(token)
                        currentArgs.clear()
                    }
                    "Tj" -> {
                        val totalMatrix = textMatrix.multiply(ctm)
                        val userX = totalMatrix.translateX
                        val userY = totalMatrix.translateY

                        val cosString = currentArgs.firstOrNull() as? COSString
                        val rawStr = cosString?.string ?: ""
                        val decodedText = decodeString(page, currentFontName, cosString, rawStr)

                        val stringWidth = estimateStringWidth(decodedText, currentFontSize)

                        val matched = userTargets.any { target ->
                            isTargetMatch(userX, userY, stringWidth, currentFontSize, target, decodedText)
                        }

                        if (matched) {
                            purgedCount++
                            val advanceMatrix = Matrix.getTranslateInstance(stringWidth, 0f)
                            textMatrix = advanceMatrix.multiply(textMatrix)
                        } else {
                            newTokens.addAll(currentArgs)
                            newTokens.add(token)
                            val advanceMatrix = Matrix.getTranslateInstance(stringWidth, 0f)
                            textMatrix = advanceMatrix.multiply(textMatrix)
                        }
                        currentArgs.clear()
                    }
                    "TJ" -> {
                        val totalMatrix = textMatrix.multiply(ctm)
                        var currentX = totalMatrix.translateX
                        val userY = totalMatrix.translateY

                        val cosArray = currentArgs.firstOrNull() as? COSArray
                        if (cosArray != null) {
                            val filteredArray = COSArray()
                            var anyPurgedInTJ = false

                            for (i in 0 until cosArray.size()) {
                                val item = cosArray.get(i)
                                if (item is COSString) {
                                    val decoded = decodeString(page, currentFontName, item, item.string)
                                    val itemWidth = estimateStringWidth(decoded, currentFontSize)

                                    val matched = userTargets.any { target ->
                                        isTargetMatch(currentX, userY, itemWidth, currentFontSize, target, decoded)
                                    }

                                    if (matched) {
                                        anyPurgedInTJ = true
                                        purgedCount++
                                        currentX += itemWidth
                                    } else {
                                        filteredArray.add(item)
                                        currentX += itemWidth
                                    }
                                } else if (item is COSNumber) {
                                    val kerning = -item.floatValue() / 1000f * currentFontSize
                                    currentX += kerning
                                    filteredArray.add(item)
                                } else {
                                    filteredArray.add(item)
                                }
                            }

                            val advanceW = currentX - totalMatrix.translateX
                            val advanceMatrix = Matrix.getTranslateInstance(advanceW, 0f)
                            textMatrix = advanceMatrix.multiply(textMatrix)

                            if (filteredArray.size() > 0) {
                                newTokens.add(filteredArray)
                                newTokens.add(token)
                            }
                        } else {
                            newTokens.addAll(currentArgs)
                            newTokens.add(token)
                        }
                        currentArgs.clear()
                    }
                    "'" -> {
                        val tdMatrix = Matrix.getTranslateInstance(0f, -textLeading)
                        textLineMatrix = tdMatrix.multiply(textLineMatrix)
                        textMatrix = textLineMatrix.clone()

                        val totalMatrix = textMatrix.multiply(ctm)
                        val userX = totalMatrix.translateX
                        val userY = totalMatrix.translateY

                        val cosString = currentArgs.firstOrNull() as? COSString
                        val rawStr = cosString?.string ?: ""
                        val decodedText = decodeString(page, currentFontName, cosString, rawStr)
                        val stringWidth = estimateStringWidth(decodedText, currentFontSize)

                        val matched = userTargets.any { target ->
                            isTargetMatch(userX, userY, stringWidth, currentFontSize, target, decodedText)
                        }

                        if (matched) {
                            purgedCount++
                            val advanceMatrix = Matrix.getTranslateInstance(stringWidth, 0f)
                            textMatrix = advanceMatrix.multiply(textMatrix)
                        } else {
                            newTokens.addAll(currentArgs)
                            newTokens.add(token)
                            val advanceMatrix = Matrix.getTranslateInstance(stringWidth, 0f)
                            textMatrix = advanceMatrix.multiply(textMatrix)
                        }
                        currentArgs.clear()
                    }
                    "\"" -> {
                        if (currentArgs.size >= 3) {
                            val tx = getFloat(currentArgs[0])
                            val ty = getFloat(currentArgs[1])
                            val tdMatrix = Matrix.getTranslateInstance(tx, ty)
                            textLineMatrix = tdMatrix.multiply(textLineMatrix)
                            textMatrix = textLineMatrix.clone()
                        }

                        val totalMatrix = textMatrix.multiply(ctm)
                        val userX = totalMatrix.translateX
                        val userY = totalMatrix.translateY

                        val cosString = currentArgs.lastOrNull() as? COSString
                        val rawStr = cosString?.string ?: ""
                        val decodedText = decodeString(page, currentFontName, cosString, rawStr)
                        val stringWidth = estimateStringWidth(decodedText, currentFontSize)

                        val matched = userTargets.any { target ->
                            isTargetMatch(userX, userY, stringWidth, currentFontSize, target, decodedText)
                        }

                        if (matched) {
                            purgedCount++
                            newTokens.add(Operator.getOperator("T*"))
                        } else {
                            newTokens.addAll(currentArgs)
                            newTokens.add(token)
                        }
                        currentArgs.clear()
                    }
                    else -> {
                        newTokens.addAll(currentArgs)
                        newTokens.add(token)
                        currentArgs.clear()
                    }
                }
            }
        }

        return Pair(newTokens, purgedCount)
    }

    private fun isTargetMatch(
        userX: Float,
        userY: Float,
        width: Float,
        fontSize: Float,
        target: UserTarget,
        text: String
    ): Boolean {
        val stringX0 = userX
        val stringX1 = userX + width

        // Vertical overlap with baseline/box
        val verticalOverlap = (userY >= target.pdfY0 - 5f && userY <= target.pdfY1 + 5f)

        // Horizontal overlap with target bounding box
        val horizontalOverlap = max(stringX0, target.pdfX0) <= min(stringX1, target.pdfX1) + 3f

        val cleanText = text.trim()
        val cleanTarget = target.originalText

        // Content match check with horizontal proximity safeguard
        val horizontalProximity = max(stringX0, target.pdfX0) <= min(stringX1, target.pdfX1) + 40f
        val textMatch = cleanTarget.isNotEmpty() && cleanText.isNotEmpty() && (
            cleanTarget.contains(cleanText, ignoreCase = true) ||
            cleanText.contains(cleanTarget, ignoreCase = true)
        )

        return (verticalOverlap && horizontalOverlap) || (verticalOverlap && horizontalProximity && textMatch)
    }

    private fun decodeString(page: PDPage, fontName: String?, cosString: COSString?, rawStr: String): String {
        if (cosString == null) return rawStr
        if (fontName != null) {
            try {
                val font = page.resources?.getFont(COSName.getPDFName(fontName))
                if (font != null) {
                    val sb = StringBuilder()
                    for (b in cosString.bytes) {
                        val code = b.toInt() and 0xFF
                        val u = font.toUnicode(code)
                        if (u != null) sb.append(u) else sb.append(code.toChar())
                    }
                    if (sb.isNotEmpty()) return sb.toString()
                }
            } catch (_: Exception) {}
        }
        return rawStr
    }

    private fun estimateStringWidth(text: String, fontSize: Float): Float {
        return text.length * fontSize * 0.5f
    }

    private fun getFloat(base: COSBase): Float {
        return when (base) {
            is COSNumber -> base.floatValue()
            else -> 0f
        }
    }
}
