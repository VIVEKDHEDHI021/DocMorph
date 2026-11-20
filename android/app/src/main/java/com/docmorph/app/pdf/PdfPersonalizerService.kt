package com.docmorph.app.pdf

import android.content.Context
import com.docmorph.app.db.AppDatabase
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.pdmodel.PDPageContentStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest
import kotlin.math.max
import kotlin.math.min

data class PersonalizationCandidate(
    val pageIndex: Int, // 0-based
    val fieldType: String,
    val originalValue: String,
    val replacementValue: String,
    val rawBbox: List<Float>, // [x0, y0, x1, y1] in top-down PDF points
    val pairId: String? = null,
    val isInverted: Boolean = false,
    val isOcr: Boolean = false,
    val fontName: String? = null,
    val fontSize: Float = 10f
)

data class PersonalizationResult(
    val success: Boolean,
    val documentId: String,
    val originalSha256: String,
    val personalizedSha256: String,
    val personalizedPath: String,
    val totalReplaced: Int,
    val verificationReport: OutputVerificationReport,
    val warnings: List<String>
)

class PdfPersonalizerService(private val context: Context) {

    private val db = AppDatabase.getDatabase(context)
    private val redactor = ContentStreamRedactor()
    private val formatter = TypographyFormatter()
    private val verifier = OutputVerifier()

    private val originalsDir: File = File(context.filesDir, "originals").apply { if (!exists()) mkdirs() }
    private val personalizedDir: File = File(context.filesDir, "personalized").apply { if (!exists()) mkdirs() }

    init {
        PDFBoxResourceLoader.init(context.applicationContext)
    }

    suspend fun personalizeDocument(
        documentId: String,
        candidates: List<PersonalizationCandidate>
    ): PersonalizationResult = withContext(Dispatchers.IO) {
        val originalFile = File(originalsDir, "$documentId.pdf")
        if (!originalFile.exists()) {
            throw IllegalArgumentException("Original PDF not found for document $documentId at ${originalFile.absolutePath}")
        }

        // Step 1: Compute SHA-256 before modification to guarantee source immutability
        val shaBefore = computeSha256(originalFile)

        val personalizedFile = File(personalizedDir, "${documentId}_personalized.pdf")
        val warnings = mutableListOf<String>()
        var totalReplaced = 0

        val verificationTargets = mutableListOf<VerificationTarget>()

        PDDocument.load(originalFile).use { doc ->
            val pageCount = doc.numberOfPages
            val candidatesByPage = candidates.groupBy { it.pageIndex }

            for ((pageIdx, pageCandidates) in candidatesByPage) {
                if (pageIdx >= pageCount) continue

                val page = doc.getPage(pageIdx)
                val cropBox = page.cropBox ?: page.mediaBox
                val pageHeight = cropBox.height
                val pageWidth = cropBox.width

                // Partition candidates into paired groups and standalone items
                val pairedGroups = mutableMapOf<String, MutableList<PersonalizationCandidate>>()
                val standaloneItems = mutableListOf<PersonalizationCandidate>()

                for (cand in pageCandidates) {
                    val pid = cand.pairId
                    if (!pid.isNullOrEmpty()) {
                        pairedGroups.getOrPut(pid) { mutableListOf() }.add(cand)
                    } else {
                        standaloneItems.add(cand)
                    }
                }

                // Collect all redaction targets for content-stream rewriting
                val pageRedactionTargets = mutableListOf<RedactionTarget>()

                // Handle paired groups (e.g. Student Name + Enrollment Number on same footer line)
                val stagedPairedInserts = mutableListOf<PairedInsertTask>()

                for ((pairId, groupList) in pairedGroups) {
                    val nameCand = groupList.firstOrNull { it.fieldType == "student_name" }
                    val idCand = groupList.firstOrNull { it.fieldType != "student_name" }

                    if (nameCand != null && idCand != null) {
                        // Reconstruct unified string
                        val newName = formatter.sanitizeAsciiText(nameCand.replacementValue.trim())
                        val newId = formatter.sanitizeAsciiText(idCand.replacementValue.trim())

                        val origCombined = "${nameCand.originalValue} ${idCand.originalValue}"
                        val isDelimiter = origCombined.contains("-") || origCombined.contains("–")

                        val unifiedText = when {
                            nameCand.isInverted || idCand.isInverted -> {
                                if (isDelimiter) "$newId - $newName" else "($newId) $newName"
                            }
                            isDelimiter -> "$newName - $newId"
                            else -> "$newName ($newId)"
                        }

                        val lineX0 = min(nameCand.rawBbox[0], idCand.rawBbox[0])
                        val lineY0 = min(nameCand.rawBbox[1], idCand.rawBbox[1])
                        val lineX1 = max(nameCand.rawBbox[2], idCand.rawBbox[2])
                        val lineY1 = max(nameCand.rawBbox[3], idCand.rawBbox[3])

                        pageRedactionTargets.add(RedactionTarget(nameCand.originalValue, nameCand.rawBbox, pageIdx))
                        pageRedactionTargets.add(RedactionTarget(idCand.originalValue, idCand.rawBbox, pageIdx))
                        pageRedactionTargets.add(RedactionTarget(origCombined, listOf(lineX0, lineY0, lineX1, lineY1), pageIdx))

                        val font = formatter.resolveFont(nameCand.fontName ?: idCand.fontName)
                        val baseSize = if (nameCand.fontSize > 0f) nameCand.fontSize else idCand.fontSize
                        val availableW = max(lineX1 - lineX0, pageWidth * 0.55f - lineX0)
                        val fitted = formatter.calculateFittedFontSize(unifiedText, font, baseSize, availableW)

                        if (fitted.warningMessage != null) {
                            warnings.add("Page ${pageIdx + 1}: ${fitted.warningMessage}")
                        }

                        stagedPairedInserts.add(
                            PairedInsertTask(
                                text = unifiedText,
                                font = fitted.font,
                                fontSize = fitted.fontSize,
                                originX = lineX0,
                                originY = pageHeight - lineY1,
                                isOcr = nameCand.isOcr || idCand.isOcr,
                                rectX0 = lineX0,
                                rectY0 = pageHeight - lineY1,
                                rectW = max(lineX1 - lineX0, fitted.textWidth),
                                rectH = max(lineY1 - lineY0, fitted.fontSize * 1.2f)
                            )
                        )

                        verificationTargets.add(VerificationTarget(pageIdx, nameCand.originalValue, nameCand.replacementValue, nameCand.rawBbox))
                        verificationTargets.add(VerificationTarget(pageIdx, idCand.originalValue, idCand.replacementValue, idCand.rawBbox))
                        totalReplaced += 2
                    } else {
                        // Orphaned pair member falls back to standalone
                        standaloneItems.addAll(groupList)
                    }
                }

                // Handle standalone items
                val stagedSingleInserts = mutableListOf<SingleInsertTask>()

                for (cand in standaloneItems) {
                    val safeText = formatter.sanitizeAsciiText(cand.replacementValue.trim())
                    pageRedactionTargets.add(RedactionTarget(cand.originalValue, cand.rawBbox, pageIdx))

                    val font = formatter.resolveFont(cand.fontName)
                    val baseSize = cand.fontSize
                    val candW = cand.rawBbox[2] - cand.rawBbox[0]
                    val candH = cand.rawBbox[3] - cand.rawBbox[1]
                    val availableW = max(candW, pageWidth * 0.45f)
                    val fitted = formatter.calculateFittedFontSize(safeText, font, baseSize, availableW)

                    if (fitted.warningMessage != null) {
                        warnings.add("Page ${pageIdx + 1}: ${fitted.warningMessage}")
                    }

                    stagedSingleInserts.add(
                        SingleInsertTask(
                            text = safeText,
                            font = fitted.font,
                            fontSize = fitted.fontSize,
                            originX = cand.rawBbox[0],
                            originY = pageHeight - cand.rawBbox[3],
                            isOcr = cand.isOcr,
                            rectX0 = cand.rawBbox[0],
                            rectY0 = pageHeight - cand.rawBbox[3],
                            rectW = max(candW, fitted.textWidth),
                            rectH = max(candH, fitted.fontSize * 1.2f)
                        )
                    )

                    verificationTargets.add(VerificationTarget(pageIdx, cand.originalValue, cand.replacementValue, cand.rawBbox))
                    totalReplaced++
                }

                // Step 2: Purge content-stream text tokens (true deletion, vector preservation)
                redactor.redactPage(doc, page, pageRedactionTargets)

                // Step 3: Insert replacement text
                PDPageContentStream(doc, page, PDPageContentStream.AppendMode.APPEND, true, true).use { cs ->
                    // 3a. Draw raster patch if scanned
                    for (task in stagedPairedInserts) {
                        if (task.isOcr) {
                            cs.setNonStrokingColor(1f, 1f, 1f)
                            cs.addRect(task.rectX0 - 2f, task.rectY0 - 2f, task.rectW + 4f, task.rectH + 4f)
                            cs.fill()
                        }
                    }
                    for (task in stagedSingleInserts) {
                        if (task.isOcr) {
                            cs.setNonStrokingColor(1f, 1f, 1f)
                            cs.addRect(task.rectX0 - 2f, task.rectY0 - 2f, task.rectW + 4f, task.rectH + 4f)
                            cs.fill()
                        }
                    }

                    // 3b. Draw paired text lines
                    for (task in stagedPairedInserts) {
                        cs.beginText()
                        cs.setNonStrokingColor(0f, 0f, 0f)
                        cs.setFont(task.font, task.fontSize)
                        cs.newLineAtOffset(task.originX, task.originY)
                        cs.showText(task.text)
                        cs.endText()
                    }

                    // 3c. Draw single text replacements
                    for (task in stagedSingleInserts) {
                        cs.beginText()
                        cs.setNonStrokingColor(0f, 0f, 0f)
                        cs.setFont(task.font, task.fontSize)
                        cs.newLineAtOffset(task.originX, task.originY)
                        cs.showText(task.text)
                        cs.endText()
                    }
                }
            }

            // Save to unique personalized file
            doc.save(personalizedFile)
        }

        // Step 4: Verify source PDF was not mutated
        val shaAfter = computeSha256(originalFile)
        if (shaBefore != shaAfter) {
            personalizedFile.delete()
            throw IllegalStateException("CRITICAL: Original PDF was mutated during personalization!")
        }

        // Step 5: Independent output verification
        val verificationReport = verifier.verifyOutput(
            outputFile = personalizedFile,
            expectedPageCount = PDDocument.load(personalizedFile).use { it.numberOfPages },
            targets = verificationTargets
        )

        val personalizedSha256 = computeSha256(personalizedFile)

        // Step 6: Update document record in Room DB
        val existing = db.documentDao().getDocumentById(documentId)
        if (existing != null) {
            db.documentDao().updateDocument(
                existing.copy(
                    personalizedPath = personalizedFile.absolutePath,
                    status = "PERSONALIZED",
                    updatedAt = System.currentTimeMillis()
                )
            )
        }

        PersonalizationResult(
            success = true,
            documentId = documentId,
            originalSha256 = shaBefore,
            personalizedSha256 = personalizedSha256,
            personalizedPath = personalizedFile.absolutePath,
            totalReplaced = totalReplaced,
            verificationReport = verificationReport,
            warnings = warnings
        )
    }

    private data class PairedInsertTask(
        val text: String,
        val font: com.tom_roush.pdfbox.pdmodel.font.PDFont,
        val fontSize: Float,
        val originX: Float,
        val originY: Float,
        val isOcr: Boolean,
        val rectX0: Float,
        val rectY0: Float,
        val rectW: Float,
        val rectH: Float
    )

    private data class SingleInsertTask(
        val text: String,
        val font: com.tom_roush.pdfbox.pdmodel.font.PDFont,
        val fontSize: Float,
        val originX: Float,
        val originY: Float,
        val isOcr: Boolean,
        val rectX0: Float,
        val rectY0: Float,
        val rectW: Float,
        val rectH: Float
    )

    private fun computeSha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { fis ->
            val buffer = ByteArray(8192)
            var bytesRead: Int
            while (fis.read(buffer).also { bytesRead = it } != -1) {
                digest.update(buffer, 0, bytesRead)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}

