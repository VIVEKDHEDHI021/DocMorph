package com.docmorph.app.detection

import com.docmorph.app.ai.OnnxLayoutInferenceService
import com.docmorph.app.pdf.ExtractionResult
import com.docmorph.app.pdf.NativeTextBlock
import java.io.File
import java.util.UUID
import kotlin.math.abs

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
        val candidates = mutableListOf<DetectionCandidate>()

        for (page in extractedData.pages) {
            val pageIndex = page.pageNumber - 1
            val pageHeight = page.height
            val pageWidth = page.width

            // 1. Detect footer boundary for this page
            val footerBoundary = footerDetector.detectFooterBoundary(pdfFile, pageIndex, pageHeight, page.blocks)
            val footerBoundaryY = footerBoundary.boundaryY

            // 2. Run unlabelled pair detector on blocks in this page
            val unlabelledPairs = unlabelledDetector.detectUnlabelledPairs(page.blocks)
            val matchedBlockTexts = mutableSetOf<String>()

            for (pair in unlabelledPairs) {
                matchedBlockTexts.add(pair.nameBlock.text)

                // Name candidate
                val normBoxName = pair.nameBlock.bbox.map { it.toInt() }
                val isBelowDivider = pair.nameBlock.rawBbox[1] >= footerBoundaryY || footerBoundary.hasDividerLine
                val nameConf = if (isBelowDivider) pair.confidence else pair.confidence * 0.9f

                candidates.add(
                    DetectionCandidate(
                        id = UUID.randomUUID().toString(),
                        fieldType = "student_name",
                        detectedText = pair.name,
                        replacementText = savedProfile?.get("fullName"),
                        confidence = nameConf,
                        pageIndex = pageIndex,
                        normalizedBox = normBoxName,
                        pdfPointBox = pair.nameBlock.rawBbox,
                        fontName = pair.nameBlock.fontName,
                        fontSize = pair.nameBlock.fontSize,
                        pairId = pair.pairId,
                        requiresConfirmation = nameConf < 0.85f
                    )
                )

                // Identifier candidate
                val normBoxId = pair.idBlock.bbox.map { it.toInt() }
                val idConf = if (isBelowDivider) pair.confidence else pair.confidence * 0.9f
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
                        confidence = idConf,
                        pageIndex = pageIndex,
                        normalizedBox = normBoxId,
                        pdfPointBox = pair.idBlock.rawBbox,
                        fontName = pair.idBlock.fontName,
                        fontSize = pair.idBlock.fontSize,
                        pairId = pair.pairId,
                        requiresConfirmation = idConf < 0.85f
                    )
                )
            }

            // 3. For blocks not matched by unlabelled regex pairs, apply ONNX / Layout inference
            val remainingBlocks = page.blocks.filter { !matchedBlockTexts.contains(it.text) }
            if (remainingBlocks.isNotEmpty()) {
                val tokens = remainingBlocks.map { it.text }
                val bboxes = remainingBlocks.map { block -> block.bbox.map { it.toInt() } }

                val layoutEntities = onnxService.predictPage(tokens, bboxes, pageHeight)

                for (entity in layoutEntities) {
                    if (entity.entityType == "footer_region" || entity.entityType == "page_number" || entity.entityType == "o") {
                        continue
                    }

                    // Map entity back to source text block
                    val firstTokenIdx = entity.tokenIndices.firstOrNull() ?: 0
                    val sourceBlock = remainingBlocks.getOrNull(firstTokenIdx) ?: remainingBlocks[0]

                    val replVal = when (entity.entityType) {
                        "student_name" -> savedProfile?.get("fullName")
                        "enrollment_number" -> savedProfile?.get("enrollmentNumber")
                        "roll_number" -> savedProfile?.get("rollNumber")
                        "student_id" -> savedProfile?.get("studentId")
                        else -> null
                    }

                    val isFooterY = sourceBlock.rawBbox[1] >= footerBoundaryY
                    var conf = entity.confidence
                    if (isFooterY) conf = (conf + 0.1f).coerceAtMost(0.99f)

                    candidates.add(
                        DetectionCandidate(
                            id = UUID.randomUUID().toString(),
                            fieldType = entity.entityType,
                            detectedText = entity.value,
                            replacementText = replVal,
                            confidence = conf,
                            pageIndex = pageIndex,
                            normalizedBox = entity.normalizedBbox,
                            pdfPointBox = sourceBlock.rawBbox,
                            fontName = sourceBlock.fontName,
                            fontSize = sourceBlock.fontSize,
                            pairId = null,
                            requiresConfirmation = conf < 0.85f
                        )
                    )
                }
            }
        }

        // 4. Cross-page consistency boosting
        return boostCrossPageConsistency(candidates)
    }

    /**
     * Cross-page consistency: If identical text or patterns repeat across pages at similar coordinates, boost confidence.
     */
    fun boostCrossPageConsistency(candidates: List<DetectionCandidate>): List<DetectionCandidate> {
        val groupedByValue = candidates.groupBy { "${it.fieldType}:${it.detectedText.lowercase()}" }

        return candidates.map { cand ->
            val group = groupedByValue["${cand.fieldType}:${cand.detectedText.lowercase()}"] ?: listOf(cand)
            if (group.size > 1) {
                // Occurs across multiple pages
                val boostedConf = (cand.confidence + 0.08f).coerceAtMost(0.99f)
                cand.copy(
                    confidence = boostedConf,
                    requiresConfirmation = boostedConf < 0.85f
                )
            } else {
                cand
            }
        }
    }
}

