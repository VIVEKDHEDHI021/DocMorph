package com.docmorph.app.detection

import com.docmorph.app.pdf.NativePageResult
import com.docmorph.app.pdf.NativeTextBlock
import java.util.UUID
import kotlin.math.max
import kotlin.math.min

class SmartManualDetector(
    private val footerDetector: FooterRegionDetector = FooterRegionDetector(),
    private val unlabelledDetector: UnlabelledIdentityDetector = UnlabelledIdentityDetector()
) {

    fun processSelection(
        input: ManualSelectionInput,
        pageData: NativePageResult,
        savedProfile: Map<String, String?>? = null
    ): ManualDetectionResult {
        val pageWidth = input.pageWidth
        val pageHeight = input.pageHeight

        // 1. Resolve and validate coordinates
        val resolvedBox = resolveCoordinates(input, pageData, pageWidth, pageHeight)
        if (resolvedBox == null) {
            return ManualDetectionResult(
                documentId = input.documentId,
                pageIndex = input.pageIndex,
                selectionType = input.selectionType,
                resolvedPdfBox = listOf(0f, 0f, 0f, 0f),
                extractedText = "",
                footerStatus = FooterStatus.FOOTER_NOT_FOUND,
                confidence = 0.90f,
                candidates = emptyList(),
                negativeReasons = listOf("Invalid or out-of-bounds selection coordinates"),
                summaryMessage = "The selection coordinates are invalid or out of page bounds."
            )
        }

        // 2. Filter blocks strictly inside the selection boundary
        val selectedBlocks = filterBlocksInside(pageData.blocks, resolvedBox)
        val extractedText = selectedBlocks.joinToString(" ") { it.text.trim() }.trim()

        if (selectedBlocks.isEmpty() || extractedText.isBlank()) {
            return ManualDetectionResult(
                documentId = input.documentId,
                pageIndex = input.pageIndex,
                selectionType = input.selectionType,
                resolvedPdfBox = resolvedBox,
                extractedText = "",
                footerStatus = FooterStatus.FOOTER_NOT_FOUND,
                confidence = 0.90f,
                candidates = emptyList(),
                negativeReasons = listOf("No text found inside the selected region"),
                summaryMessage = "The selected region does not contain any readable text."
            )
        }

        // 3. Apply Phase B Footer Verification
        val verification = verifySelection(selectedBlocks, resolvedBox, pageHeight)
        val status = verification.status
        val confidence = verification.confidence
        val negativeReasons = verification.negativeReasons

        // 4. Extract Student Information Candidates if verified
        val candidates = mutableListOf<DetectionCandidate>()

        if (status == FooterStatus.FOOTER_CONFIRMED || status == FooterStatus.FOOTER_UNCERTAIN) {
            val isUncertain = (status == FooterStatus.FOOTER_UNCERTAIN)
            val extracted = extractCandidates(
                input.pageIndex,
                selectedBlocks,
                isUncertain,
                savedProfile
            )
            candidates.addAll(extracted)
        }

        val summaryMsg = when {
            status == FooterStatus.FOOTER_CONFIRMED && candidates.isEmpty() ->
                "A possible footer was identified, but no supported student information could be found."
            status == FooterStatus.FOOTER_CONFIRMED ->
                "Recognizable footer verified. Identified ${candidates.size} student field(s)."
            status == FooterStatus.FOOTER_UNCERTAIN ->
                "Footer needs review. Identified partial candidate information requiring confirmation."
            else ->
                "The selected region does not appear to contain recognizable footer information."
        }

        return ManualDetectionResult(
            documentId = input.documentId,
            pageIndex = input.pageIndex,
            selectionType = input.selectionType,
            resolvedPdfBox = resolvedBox,
            extractedText = extractedText,
            footerStatus = status,
            confidence = confidence,
            candidates = candidates,
            negativeReasons = negativeReasons,
            summaryMessage = summaryMsg
        )
    }

    private fun resolveCoordinates(
        input: ManualSelectionInput,
        pageData: NativePageResult,
        pageWidth: Float,
        pageHeight: Float
    ): List<Float>? {
        var x0 = 0f
        var y0 = 0f
        var x1 = 0f
        var y1 = 0f

        when (input.selectionType) {
            SelectionType.AREA -> {
                if (input.rawBbox != null && input.rawBbox.size == 4) {
                    x0 = input.rawBbox[0]
                    y0 = input.rawBbox[1]
                    x1 = input.rawBbox[2]
                    y1 = input.rawBbox[3]
                } else if (input.normalizedBox != null && input.normalizedBox.size == 4) {
                    x0 = (input.normalizedBox[0] / 1000f) * pageWidth
                    y0 = (input.normalizedBox[1] / 1000f) * pageHeight
                    x1 = (input.normalizedBox[2] / 1000f) * pageWidth
                    y1 = (input.normalizedBox[3] / 1000f) * pageHeight
                } else {
                    return null
                }
            }
            SelectionType.TEXT -> {
                if (input.rawBbox != null && input.rawBbox.size == 4) {
                    x0 = max(0f, input.rawBbox[0] - 8f)
                    y0 = max(0f, input.rawBbox[1] - 4f)
                    x1 = min(pageWidth, input.rawBbox[2] + 8f)
                    y1 = min(pageHeight, input.rawBbox[3] + 4f)
                } else if (!input.selectedText.isNullOrBlank()) {
                    // Match selectedText against extracted page blocks
                    val match = pageData.blocks.firstOrNull { it.text.contains(input.selectedText.trim()) }
                    if (match != null) {
                        x0 = max(0f, match.rawBbox[0] - 8f)
                        y0 = max(0f, match.rawBbox[1] - 4f)
                        x1 = min(pageWidth, match.rawBbox[2] + 8f)
                        y1 = min(pageHeight, match.rawBbox[3] + 4f)
                    } else {
                        return null
                    }
                } else {
                    return null
                }
            }
        }

        if (x1 <= x0 || y1 <= y0) return null
        val w = x1 - x0
        val h = y1 - y0
        if (w * h < 15f) return null

        val clampedX0 = max(0f, min(pageWidth, x0))
        val clampedY0 = max(0f, min(pageHeight, y0))
        val clampedX1 = max(0f, min(pageWidth, x1))
        val clampedY1 = max(0f, min(pageHeight, y1))

        return listOf(clampedX0, clampedY0, clampedX1, clampedY1)
    }

    private fun filterBlocksInside(
        blocks: List<NativeTextBlock>,
        box: List<Float>
    ): List<NativeTextBlock> {
        val bx0 = box[0]
        val by0 = box[1]
        val bx1 = box[2]
        val by1 = box[3]

        return blocks.filter { block ->
            val b = block.rawBbox
            val midX = (b[0] + b[2]) / 2f
            val midY = (b[1] + b[3]) / 2f

            // Check if center is contained
            if (midX in bx0..bx1 && midY in by0..by1) {
                true
            } else {
                // Check if significant overlap (> 40% area)
                val ox0 = max(bx0, b[0])
                val oy0 = max(by0, b[1])
                val ox1 = min(bx1, b[2])
                val oy1 = min(by1, b[3])

                if (ox1 > ox0 && oy1 > oy0) {
                    val overlapArea = (ox1 - ox0) * (oy1 - oy0)
                    val blockArea = (b[2] - b[0]) * (b[3] - b[1])
                    blockArea > 0f && (overlapArea / blockArea) >= 0.40f
                } else {
                    false
                }
            }
        }
    }

    private data class VerificationResult(
        val status: FooterStatus,
        val confidence: Float,
        val negativeReasons: List<String>
    )

    private fun verifySelection(
        blocks: List<NativeTextBlock>,
        box: List<Float>,
        pageHeight: Float
    ): VerificationResult {
        val texts = blocks.map { it.text.trim() }.filter { it.isNotEmpty() }
        val combined = texts.joinToString(" ")
        val combinedLower = combined.lowercase()

        var negativeScore = 0f
        var layoutScore = 0f
        var semanticScore = 0f
        val negativeReasons = mutableListOf<String>()

        // 1. Negative keywords
        for (kw in FooterRegionDetector.NEGATIVE_KEYWORDS) {
            if (Regex("""\b${Regex.escape(kw)}\b""").containsMatchIn(combinedLower)) {
                negativeScore += 40f
                negativeReasons.add("Contains negative academic keyword: '$kw'")
                break
            }
        }

        // 2. Experiment / Chapter / Section
        if (FooterRegionDetector.RE_EXP_CHAPTER.containsMatchIn(combined)) {
            negativeScore += 45f
            negativeReasons.add("Contains experiment/chapter pattern: '${combined.take(25)}'")
        }

        // 3. Solitary Page Number
        if (texts.size == 1 && FooterRegionDetector.RE_SOLITARY_PAGE_NUMBER.matches(texts[0])) {
            negativeScore += 45f
            negativeReasons.add("Solitary page number alone (not a student footer)")
        }

        // 4. Prose / Running Sentences
        val proseCount = FooterRegionDetector.RE_PROSE_WORDS.findAll(combined).count()
        if (proseCount >= 3 || (combined.split(Regex("""\s+""")).size > 14 && combined.endsWith("."))) {
            negativeScore += 40f
            negativeReasons.add("Prose-like running sentence structure ($proseCount prose words)")
        }

        // 5. Layout Signals
        if (blocks.size in 1..2) {
            layoutScore += 25f
        } else if (blocks.size >= 5) {
            negativeScore += 30f
            negativeReasons.add("Selected area contains ${blocks.size} lines (typical footers are 1-2 lines)")
        }

        if (box[1] >= pageHeight * 0.75f) {
            layoutScore += 25f
        } else if (box[1] >= pageHeight * 0.65f) {
            layoutScore += 10f
        } else {
            negativeScore += 25f
            negativeReasons.add("Selected area is located in top/middle body region (y0 < 65% page height)")
        }

        // 6. Semantic Signals
        val hasIdPair = Regex("""([A-Za-z\s.'-]{3,35})\s*[\(\[]\s*(\d{6,18}|[A-Za-z0-9\-_]{5,20})\s*[\)\]]""").containsMatchIn(combined) ||
                        Regex("""([A-Za-z\s.'-]{3,35})\s*[-–—|]\s*(\d{6,18})""").containsMatchIn(combined)
        if (hasIdPair && negativeScore < 35f) {
            semanticScore += 35f
        }

        val hasLabels = Regex("""(?i)\b(?:name|enrollment(?:\s*no\.?)?|roll(?:\s*no\.?)?|student\s*id)\s*:""").containsMatchIn(combined)
        if (hasLabels && negativeScore < 35f) {
            semanticScore += 30f
        }

        if (negativeScore == 0f) {
            layoutScore += 15f
        }

        val netScore = (layoutScore + semanticScore) - negativeScore

        val status: FooterStatus
        val conf: Float
        if (negativeScore >= 40f) {
            status = FooterStatus.FOOTER_NOT_FOUND
            conf = max(0.85f, min(0.99f, negativeScore / 100f))
        } else if (netScore >= 50f) {
            status = FooterStatus.FOOTER_CONFIRMED
            conf = min(0.98f, max(0.75f, netScore / 100f))
        } else if (netScore >= 20f && negativeScore < 30f) {
            status = FooterStatus.FOOTER_UNCERTAIN
            conf = 0.55f
        } else {
            status = FooterStatus.FOOTER_NOT_FOUND
            conf = 0.85f
        }

        return VerificationResult(
            status = status,
            confidence = conf,
            negativeReasons = negativeReasons.distinct()
        )
    }

    private fun extractCandidates(
        pageIndex: Int,
        blocks: List<NativeTextBlock>,
        isUncertain: Boolean,
        savedProfile: Map<String, String?>?
    ): List<DetectionCandidate> {
        val candidates = mutableListOf<DetectionCandidate>()

        // 1. Unlabelled identity pairs
        val pairs = unlabelledDetector.detectUnlabelledPairs(blocks)
        for (pair in pairs) {
            val conf = if (isUncertain) 0.65f else pair.confidence
            val requireConfirm = isUncertain || conf < 0.85f

            // Name
            candidates.add(
                DetectionCandidate(
                    id = UUID.randomUUID().toString(),
                    fieldType = "student_name",
                    detectedText = pair.name,
                    replacementText = savedProfile?.get("fullName"),
                    confidence = conf,
                    pageIndex = pageIndex,
                    normalizedBox = pair.nameBlock.bbox.map { it.toInt() },
                    pdfPointBox = pair.nameBlock.rawBbox,
                    fontName = pair.nameBlock.fontName,
                    fontSize = pair.nameBlock.fontSize,
                    pairId = pair.pairId,
                    requiresConfirmation = requireConfirm
                )
            )

            // ID
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
                    confidence = conf,
                    pageIndex = pageIndex,
                    normalizedBox = pair.idBlock.bbox.map { it.toInt() },
                    pdfPointBox = pair.idBlock.rawBbox,
                    fontName = pair.idBlock.fontName,
                    fontSize = pair.idBlock.fontSize,
                    pairId = pair.pairId,
                    requiresConfirmation = requireConfirm
                )
            )
        }

        // 2. Single item fallback (when only Name or only ID was selected)
        if (candidates.isEmpty() && blocks.size == 1) {
            val block = blocks[0]
            val clean = block.text.trim('(', ')', '[', ']', '-', '|', ',', '.', ':')

            if (unlabelledDetector.isValidStudentName(clean)) {
                candidates.add(
                    DetectionCandidate(
                        id = UUID.randomUUID().toString(),
                        fieldType = "student_name",
                        detectedText = clean,
                        replacementText = savedProfile?.get("fullName"),
                        confidence = if (isUncertain) 0.65f else 0.88f,
                        pageIndex = pageIndex,
                        normalizedBox = block.bbox.map { it.toInt() },
                        pdfPointBox = block.rawBbox,
                        fontName = block.fontName,
                        fontSize = block.fontSize,
                        pairId = null,
                        requiresConfirmation = isUncertain
                    )
                )
            } else {
                val idType = unlabelledDetector.classifyIdentifier(clean)
                if (idType != null) {
                    val replId = when (idType) {
                        "enrollment_number" -> savedProfile?.get("enrollmentNumber")
                        "roll_number" -> savedProfile?.get("rollNumber")
                        else -> savedProfile?.get("studentId")
                    }

                    candidates.add(
                        DetectionCandidate(
                            id = UUID.randomUUID().toString(),
                            fieldType = idType,
                            detectedText = clean,
                            replacementText = replId,
                            confidence = if (isUncertain) 0.65f else 0.88f,
                            pageIndex = pageIndex,
                            normalizedBox = block.bbox.map { it.toInt() },
                            pdfPointBox = block.rawBbox,
                            fontName = block.fontName,
                            fontSize = block.fontSize,
                            pairId = null,
                            requiresConfirmation = isUncertain
                        )
                    )
                }
            }
        }

        return candidates
    }
}
