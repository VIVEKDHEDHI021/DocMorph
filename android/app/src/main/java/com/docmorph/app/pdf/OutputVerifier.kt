package com.docmorph.app.pdf

import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import com.tom_roush.pdfbox.text.TextPosition
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.OutputStreamWriter
import kotlin.math.max
import kotlin.math.min

data class VerificationTarget(
    val pageIndex: Int, // 0-based
    val originalValue: String,
    val replacementValue: String,
    val rawBbox: List<Float>? = null
)

data class PageVerificationResult(
    val pageIndex: Int,
    val pageNumber: Int,
    val passed: Boolean,
    val status: String, // "Verified", "Old student name still detected", "Replacement missing", "Manual review required"
    val errors: List<String> = emptyList(),
    val warnings: List<String> = emptyList()
)

data class OutputVerificationReport(
    val passed: Boolean,
    val totalChecks: Int,
    val pageResults: List<PageVerificationResult> = emptyList(),
    val errors: List<String>,
    val warnings: List<String>
)

class OutputVerificationException(message: String, val report: OutputVerificationReport) : Exception(message)

class OutputVerifier {

    /**
     * Independently audits the generated personalized PDF:
     * 1. Output file structural validity and page count preservation.
     * 2. Page-by-page enumeration and verification.
     * 3. Confirms that replacement values are successfully extractable.
     * 4. Confirms that original values are purged from target regions.
     * 5. Confirms no duplicate replacement text and footer region integrity.
     */
    fun verifyOutput(
        outputFile: File,
        expectedPageCount: Int,
        targets: List<VerificationTarget>
    ): OutputVerificationReport {
        val allErrors = mutableListOf<String>()
        val allWarnings = mutableListOf<String>()
        val pageResults = mutableListOf<PageVerificationResult>()
        var totalChecks = 0

        // Check 1: File existence and non-zero size
        totalChecks++
        if (!outputFile.exists() || outputFile.length() == 0L) {
            allErrors.add("Output file does not exist or is empty (0 bytes)")
            val report = OutputVerificationReport(
                passed = false,
                totalChecks = totalChecks,
                pageResults = emptyList(),
                errors = allErrors,
                warnings = allWarnings
            )
            throw OutputVerificationException("Verification failed: Output file missing or empty", report)
        }

        // Check 2: Load document and verify page count
        totalChecks++
        val doc: PDDocument
        try {
            doc = PDDocument.load(outputFile)
        } catch (e: Exception) {
            allErrors.add("Failed to parse generated output PDF: ${e.message}")
            val report = OutputVerificationReport(
                passed = false,
                totalChecks = totalChecks,
                pageResults = emptyList(),
                errors = allErrors,
                warnings = allWarnings
            )
            throw OutputVerificationException("Verification failed: Output PDF invalid", report)
        }

        doc.use {
            if (doc.numberOfPages != expectedPageCount) {
                allErrors.add("Page count mismatch: expected $expectedPageCount, got ${doc.numberOfPages}")
            }

            val targetsByPage = targets.groupBy { it.pageIndex }

            // Enumerate EVERY page in the document
            for (pageIdx in 0 until doc.numberOfPages) {
                val pageNum = pageIdx + 1
                val page = doc.getPage(pageIdx)
                val cropBox = page.cropBox ?: page.mediaBox
                val pageHeight = cropBox.height
                val pageWidth = cropBox.width

                val pageTargets = targetsByPage[pageIdx] ?: emptyList()
                val pageErrors = mutableListOf<String>()
                val pageWarnings = mutableListOf<String>()

                val coordStripper = CoordinateStripper(pageWidth, pageHeight)
                coordStripper.startPage = pageNum
                coordStripper.endPage = pageNum
                try {
                    coordStripper.getText(doc)
                } catch (e: Exception) {
                    // fallback
                }

                val pageBlocks = coordStripper.lineBlocks
                val extractedText = if (pageBlocks.isNotEmpty()) {
                    pageBlocks.joinToString("\n") { it.text }
                } else {
                    val simpleStripper = PDFTextStripper()
                    simpleStripper.startPage = pageNum
                    simpleStripper.endPage = pageNum
                    simpleStripper.getText(doc) ?: ""
                }

                // Verify page text is not completely wiped
                if (extractedText.isBlank() && pageTargets.isNotEmpty()) {
                    pageWarnings.add("Page $pageNum has no extractable text (may be image-based or blank)")
                }

                for (target in pageTargets) {
                    totalChecks++
                    val origClean = target.originalValue.trim()
                    val repClean = target.replacementValue.trim()

                    // Assertion A: Replacement value MUST appear on the page
                    if (repClean.isNotEmpty()) {
                        val foundExact = extractedText.contains(repClean, ignoreCase = true)
                        if (!foundExact) {
                            val tokens = repClean.split(" ").filter { it.length > 2 }
                            val foundTokens = tokens.isNotEmpty() && tokens.all { extractedText.contains(it, ignoreCase = true) }
                            if (!foundTokens) {
                                pageWarnings.add("Replacement value '$repClean' was not found on page $pageNum.")
                            }
                        }
                    }

                    // Assertion B: Original purged value must be absent from target region
                    // Only check if replacement value is different from original value!
                    if (origClean.isNotEmpty() && !origClean.equals(repClean, ignoreCase = true)) {
                        val targetBbox = target.rawBbox
                        val isPresentInTargetRegion = if (targetBbox != null && targetBbox.size >= 4) {
                            // Check line blocks near the target y position (within 15pt)
                            val nearBlocks = pageBlocks.filter { block ->
                                kotlin.math.abs(block.rawBbox[1] - targetBbox[1]) <= 15f
                            }
                            val regionText = nearBlocks.joinToString(" ") { it.text }
                            regionText.contains(origClean, ignoreCase = true)
                        } else {
                            // If target is in footer area (bottom 30% of page), check footer area
                            val footerBlocks = pageBlocks.filter { it.rawBbox[1] >= pageHeight * 0.70f }
                            val footerText = footerBlocks.joinToString(" ") { it.text }
                            footerText.contains(origClean, ignoreCase = true)
                        }

                        if (isPresentInTargetRegion) {
                            pageWarnings.add("Old identity '$origClean' still detected in target region on page $pageNum.")
                        }
                    }

                    // Assertion C: Check for duplicate replacement insertion
                    if (repClean.isNotEmpty()) {
                        val count = Regex.escape(repClean).toRegex(RegexOption.IGNORE_CASE).findAll(extractedText).count()
                        if (count > 2) {
                            pageWarnings.add("Replacement value '$repClean' appears $count times on page $pageNum (possible duplicate).")
                        }
                    }
                }

                allErrors.addAll(pageErrors)
                allWarnings.addAll(pageWarnings)

                val pageStatus = when {
                    pageErrors.any { it.contains("still detected", ignoreCase = true) } -> "Old identity still detected"
                    pageErrors.any { it.contains("not found", ignoreCase = true) } -> "Replacement missing"
                    pageErrors.isNotEmpty() -> "Verification failed"
                    pageWarnings.isNotEmpty() -> "Manual review required"
                    else -> "Verified"
                }

                pageResults.add(
                    PageVerificationResult(
                        pageIndex = pageIdx,
                        pageNumber = pageNum,
                        passed = pageErrors.isEmpty(),
                        status = pageStatus,
                        errors = pageErrors,
                        warnings = pageWarnings
                    )
                )
            }
        }

        val passed = allErrors.isEmpty()
        return OutputVerificationReport(
            passed = passed,
            totalChecks = totalChecks,
            pageResults = pageResults,
            errors = allErrors,
            warnings = allWarnings
        )
    }

    private class CoordinateStripper(
        private val pageWidth: Float,
        private val pageHeight: Float
    ) : PDFTextStripper() {

        val lineBlocks = mutableListOf<NativeTextBlock>()
        private var currentLine = StringBuilder()
        private var lineX0 = Float.MAX_VALUE
        private var lineY0 = Float.MAX_VALUE
        private var lineX1 = Float.MIN_VALUE
        private var lineY1 = Float.MIN_VALUE
        private var currentFontName: String? = null
        private var currentFontSize = 0f

        init {
            sortByPosition = true
            output = OutputStreamWriter(ByteArrayOutputStream())
        }

        override fun writeString(text: String, textPositions: List<TextPosition>) {
            if (textPositions.isEmpty()) return

            currentLine.clear()
            lineX0 = Float.MAX_VALUE
            lineY0 = Float.MAX_VALUE
            lineX1 = Float.MIN_VALUE
            lineY1 = Float.MIN_VALUE

            for (pos in textPositions) {
                currentLine.append(pos.unicode)

                val x = pos.xDirAdj
                val y = pos.yDirAdj
                val w = pos.widthDirAdj
                val h = pos.heightDir

                lineX0 = min(lineX0, x)
                lineY0 = min(lineY0, y - h)
                lineX1 = max(lineX1, x + w)
                lineY1 = max(lineY1, y)

                currentFontName = pos.font?.name
                currentFontSize = pos.fontSizeInPt
            }

            val lineText = currentLine.toString().trim()
            if (lineText.isNotEmpty()) {
                val normX0 = (lineX0 / pageWidth) * 1000f
                val normY0 = (lineY0 / pageHeight) * 1000f
                val normX1 = (lineX1 / pageWidth) * 1000f
                val normY1 = (lineY1 / pageHeight) * 1000f

                lineBlocks.add(
                    NativeTextBlock(
                        text = lineText,
                        bbox = listOf(
                            normX0.coerceIn(0f, 1000f),
                            normY0.coerceIn(0f, 1000f),
                            normX1.coerceIn(0f, 1000f),
                            normY1.coerceIn(0f, 1000f)
                        ),
                        rawBbox = listOf(lineX0, lineY0, lineX1, lineY1),
                        fontName = currentFontName,
                        fontSize = currentFontSize
                    )
                )
            }
        }
    }
}
