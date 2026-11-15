package com.docmorph.app.detection

import com.docmorph.app.ai.OnnxLayoutInferenceService
import com.docmorph.app.pdf.ExtractionResult
import com.docmorph.app.pdf.NativeTextBlock
import java.io.File
import java.util.UUID

data class DetectionCandidate(
    val id: String = UUID.randomUUID().toString(),
    val fieldType: String, // "student_name", "enrollment_number", "roll_number", "student_id"
    val detectedText: String,
    val replacementText: String? = null,
    val confidence: Float,
    val pageIndex: Int,
    val normalizedBox: List<Int>, // [x0, y0, x1, y1] normalized to [0, 1000]
    val pdfPointBox: List<Float>, // [x0, y0, x1, y1] in points
    val fontName: String? = null,
    val fontSize: Float = 0f,
    val pairId: String? = null,
    val requiresConfirmation: Boolean = false
)

data class OrchestrationResult(
    val candidates: List<DetectionCandidate>,
    val footerVerification: DocumentFooterVerification
)

class DetectionOrchestrator(
    private val onnxService: OnnxLayoutInferenceService,
    private val footerDetector: FooterRegionDetector = FooterRegionDetector(),
    private val unlabelledDetector: UnlabelledIdentityDetector = UnlabelledIdentityDetector()
) {

    fun analyzeDocument(
        pdfFile: File,
        extractedData: ExtractionResult,
        savedProfile: Map<String, String?>? = null
    ): List<DetectionCandidate> {
        return analyzeDocumentWithVerification(pdfFile, extractedData, savedProfile).candidates
    }

    fun analyzeDocumentWithVerification(
        pdfFile: File,
        extractedData: ExtractionResult,
        savedProfile: Map<String, String?>? = null
    ): OrchestrationResult {
        val candidates = mutableListOf<DetectionCandidate>()

        val pageHeights = extractedData.pages.map { it.height }
        val pageWidths = extractedData.pages.map { it.width }
        val pagesBlocks = extractedData.pages.map { it.blocks }

        // Phase B: Document-wide & Page-level Footer Verification Layer
        val docVerification = footerDetector.verifyDocument(
            totalPages = extractedData.totalPages,
            pageHeights = pageHeights,
            pageWidths = pageWidths,
            pagesBlocks = pagesBlocks
        )

        for (page in extractedData.pages) {
            val pageIndex = page.pageNumber - 1
            val pageHeight = page.height
            val pageWidth = page.width

            val pageVerif = docVerification.pageResults.getOrNull(pageIndex)
            val pageFooterStatus = pageVerif?.status ?: FooterStatus.FOOTER_NOT_FOUND
            val footerBoundaryY = pageVerif?.boundaryY ?: (pageHeight * 0.96f)

            // If page has NO footer (FOOTER_NOT_FOUND), do NOT extract unlabelled footer identity candidates
            val isPageFooterEligible = (pageFooterStatus == FooterStatus.FOOTER_CONFIRMED || pageFooterStatus == FooterStatus.FOOTER_UNCERTAIN)

            val matchedBlockTexts = mutableSetOf<String>()

            // 1. Unlabelled identity pair detection (Strictly in verified footer zone)
            if (isPageFooterEligible) {
                // Only consider blocks situated at or below the verified footer boundary
                val footerZoneBlocks = page.blocks.filter { it.rawBbox[1] >= (footerBoundaryY - 5f) }
                val unlabelledPairs = unlabelledDetector.detectUnlabelledPairs(footerZoneBlocks)

                for (pair in unlabelledPairs) {
                    matchedBlockTexts.add(pair.nameBlock.text)

                    val isUncertain = (pageFooterStatus == FooterStatus.FOOTER_UNCERTAIN)
                    val baseConf = if (isUncertain) minOf(0.70f, pair.confidence) else pair.confidence
                    val requireConfirm = isUncertain || baseConf < 0.85f

                    // Student Name candidate
                    val normBoxName = pair.nameBlock.bbox.map { it.toInt() }
                    candidates.add(
                        DetectionCandidate(
                            id = UUID.randomUUID().toString(),
                            fieldType = "student_name",
                            detectedText = pair.name,
                            replacementText = savedProfile?.get("fullName"),
                            confidence = baseConf,
                            pageIndex = pageIndex,
                            normalizedBox = normBoxName,
                            pdfPointBox = pair.nameBlock.rawBbox,
                            fontName = pair.nameBlock.fontName,
                            fontSize = pair.nameBlock.fontSize,
                            pairId = pair.pairId,
                            requiresConfirmation = requireConfirm
                        )
                    )

                    // Identifier candidate
                    val normBoxId = pair.idBlock.bbox.map { it.toInt() }
                    val replId = when (pair.identifierType) {
                        "enrollment_number" -> savedProfile?.get("enrollmentNumber")
                        "roll_number" -> savedProfile?.get("rollNumber")
                        else -> savedProfile?.get("studentId")
                    }

                    candidates.add(
                        DetectionCandidate(
                            id = UUID.randomUUID().toString(),
                            fieldType = pair.identifierType,
                            detectedText = pair.identifier,
                            replacementText = replId,
                            confidence = baseConf,
                            pageIndex = pageIndex,
                            normalizedBox = normBoxId,
                            pdfPointBox = pair.idBlock.rawBbox,
                            fontName = pair.idBlock.fontName,
                            fontSize = pair.idBlock.fontSize,
                            pairId = pair.pairId,
                            requiresConfirmation = requireConfirm
                        )
                    )
                }
            }

            // 2. For blocks not matched by unlabelled regex pairs, apply ONNX / Layout inference
            // Only search remaining blocks within footer zone if page footer is eligible
            if (isPageFooterEligible) {
                val remainingBlocks = page.blocks.filter { block ->
                    !matchedBlockTexts.contains(block.text) && block.rawBbox[1] >= (footerBoundaryY - 5f)
                }

                if (remainingBlocks.isNotEmpty()) {
                    val tokens = remainingBlocks.map { it.text }
                    val bboxes = remainingBlocks.map { block -> block.bbox.map { it.toInt() } }

                    val layoutEntities = onnxService.predictPage(tokens, bboxes, pageHeight)

                    for (entity in layoutEntities) {
                        if (entity.entityType == "footer_region" || entity.entityType == "page_number" || entity.entityType == "o") {
                            continue
                        }

                        val firstTokenIdx = entity.tokenIndices.firstOrNull() ?: 0
                        val sourceBlock = remainingBlocks.getOrNull(firstTokenIdx) ?: remainingBlocks[0]

                        val replVal = when (entity.entityType) {
                            "student_name" -> savedProfile?.get("fullName")
                            "enrollment_number" -> savedProfile?.get("enrollmentNumber")
                            "roll_number" -> savedProfile?.get("rollNumber")
                            "student_id" -> savedProfile?.get("studentId")
                            else -> null
                        }

                        val isUncertain = (pageFooterStatus == FooterStatus.FOOTER_UNCERTAIN)
                        val finalConf = if (isUncertain) minOf(0.70f, entity.confidence) else entity.confidence

                        candidates.add(
                            DetectionCandidate(
                                id = UUID.randomUUID().toString(),
                                fieldType = entity.entityType,
                                detectedText = entity.value,
                                replacementText = replVal,
                                confidence = finalConf,
                                pageIndex = pageIndex,
                                normalizedBox = entity.normalizedBbox,
                                pdfPointBox = sourceBlock.rawBbox,
                                fontName = sourceBlock.fontName,
                                fontSize = sourceBlock.fontSize,
                                pairId = null,
                                requiresConfirmation = isUncertain || finalConf < 0.85f
                            )
                        )
                    }
                }
            }
        }

        return OrchestrationResult(
            candidates = candidates,
            footerVerification = docVerification
        )
    }
}
