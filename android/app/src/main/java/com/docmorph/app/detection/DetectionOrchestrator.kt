package com.docmorph.app.detection

import com.docmorph.app.ai.OnnxLayoutInferenceService
import com.docmorph.app.pdf.ExtractionResult
import com.docmorph.app.pdf.NativeTextBlock
import java.io.File
import java.util.UUID
import kotlin.math.max
import kotlin.math.min

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
    val requiresConfirmation: Boolean = false,
    val isOcr: Boolean = false
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

    companion object {
        // Explicit label patterns
        private val RE_LABEL_NAME = Regex("""(?i)\b(?:student\s*name|candidate\s*name|full\s*name|name\s*of\s*(?:the\s*)?student|name)\s*[:\-–—]\s*(.+)""")
        private val RE_LABEL_ENROLLMENT = Regex("""(?i)\b(?:enrollment(?:\s*no\.?|\s*number)?|enrol(?:\s*no\.?|\s*number)?|enr(?:\s*no\.?|\s*number)?|registration(?:\s*no\.?|\s*number)?|reg(?:\s*no\.?|\s*number)?)\s*[:\-–—]\s*(.+)""")
        private val RE_LABEL_ROLL = Regex("""(?i)\b(?:roll(?:\s*no\.?|\s*number)?)\s*[:\-–—]\s*(.+)""")
        private val RE_LABEL_STUDENT_ID = Regex("""(?i)\b(?:student\s*id|stu\s*id|id\s*no\.?)\s*[:\-–—]\s*(.+)""")

        private val RE_STANDALONE_NAME = Regex("""(?i)^\s*(?:student\s*name|candidate\s*name|full\s*name|name)\s*[:\-–—]?\s*$""")
        private val RE_STANDALONE_ENROLL = Regex("""(?i)^\s*(?:enrollment(?:\s*no\.?|\s*number)?|enrol(?:\s*no\.?|\s*number)?|registration(?:\s*no\.?|\s*number)?)\s*[:\-–—]?\s*$""")
        private val RE_STANDALONE_ROLL = Regex("""(?i)^\s*(?:roll(?:\s*no\.?|\s*number)?)\s*[:\-–—]?\s*$""")
        private val RE_STANDALONE_ID = Regex("""(?i)^\s*(?:student\s*id|stu\s*id)\s*[:\-–—]?\s*$""")

        fun getProfileReplacement(fieldType: String, profile: Map<String, String?>?): String? {
            if (profile == null) return null
            val fullName = profile["fullName"]
            val enrollmentNumber = profile["enrollmentNumber"]
            val rollNumber = profile["rollNumber"]
            val studentId = profile["studentId"]
            val fallbackId = if (!studentId.isNullOrBlank()) studentId else if (!enrollmentNumber.isNullOrBlank()) enrollmentNumber else rollNumber
            val fallbackRoll = if (!rollNumber.isNullOrBlank()) rollNumber else if (!enrollmentNumber.isNullOrBlank()) enrollmentNumber else studentId
            val fallbackEnroll = if (!enrollmentNumber.isNullOrBlank()) enrollmentNumber else if (!studentId.isNullOrBlank()) studentId else rollNumber

            return when (fieldType) {
                "student_name" -> fullName
                "enrollment_number" -> fallbackEnroll
                "roll_number" -> fallbackRoll
                "student_id" -> fallbackId
                else -> fallbackId
            }
        }
    }

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

        // Document-wide & Page-level Footer Verification Layer
        val docVerification = footerDetector.verifyDocument(
            totalPages = extractedData.totalPages,
            pageHeights = pageHeights,
            pageWidths = pageWidths,
            pagesBlocks = pagesBlocks
        )

        val matchedBlocksByPage = mutableMapOf<Int, MutableSet<String>>()

        // --- PASS 1: Page-by-Page Explicit Labeled Identity Detection ---
        // Evaluates every page independently (cover page, assignment header, middle pages, tables, footers)
        for (page in extractedData.pages) {
            val pageIndex = page.pageNumber - 1
            val pageHeight = page.height
            val pageWidth = page.width
            val matchedBlocks = matchedBlocksByPage.getOrPut(pageIndex) { mutableSetOf() }

            val sortedBlocks = page.blocks.sortedWith(
                compareBy<NativeTextBlock> { it.rawBbox[1] }.thenBy { it.rawBbox[0] }
            )

            for (i in sortedBlocks.indices) {
                val block = sortedBlocks[i]
                val text = block.text.trim()

                // Check for single-line labeled values
                var detectedFieldType: String? = null
                var extractedValue: String? = null

                val mEnroll = RE_LABEL_ENROLLMENT.find(text)
                val mRoll = RE_LABEL_ROLL.find(text)
                val mId = RE_LABEL_STUDENT_ID.find(text)
                val mName = RE_LABEL_NAME.find(text)

                when {
                    mEnroll != null -> {
                        detectedFieldType = "enrollment_number"
                        extractedValue = mEnroll.groupValues[1].trim()
                    }
                    mRoll != null -> {
                        detectedFieldType = "roll_number"
                        extractedValue = mRoll.groupValues[1].trim()
                    }
                    mId != null -> {
                        detectedFieldType = "student_id"
                        extractedValue = mId.groupValues[1].trim()
                    }
                    mName != null -> {
                        detectedFieldType = "student_name"
                        extractedValue = mName.groupValues[1].trim()
                    }
                }

                // Check for multi-line labels (label in block i, value in block i+1)
                if (detectedFieldType == null && i + 1 < sortedBlocks.size) {
                    val nextBlock = sortedBlocks[i + 1]
                    val nextText = nextBlock.text.trim()
                    val yGap = nextBlock.rawBbox[1] - block.rawBbox[3]

                    if (yGap in -2f..30f) {
                        when {
                            RE_STANDALONE_ENROLL.matches(text) -> {
                                detectedFieldType = "enrollment_number"
                                extractedValue = nextText
                                matchedBlocks.add(nextBlock.text)
                            }
                            RE_STANDALONE_ROLL.matches(text) -> {
                                detectedFieldType = "roll_number"
                                extractedValue = nextText
                                matchedBlocks.add(nextBlock.text)
                            }
                            RE_STANDALONE_ID.matches(text) -> {
                                detectedFieldType = "student_id"
                                extractedValue = nextText
                                matchedBlocks.add(nextBlock.text)
                            }
                            RE_STANDALONE_NAME.matches(text) -> {
                                detectedFieldType = "student_name"
                                extractedValue = nextText
                                matchedBlocks.add(nextBlock.text)
                            }
                        }
                    }
                }

                if (detectedFieldType != null && !extractedValue.isNullOrBlank()) {
                    val cleanValue = cleanExtractedValue(extractedValue)

                    val isValid = when (detectedFieldType) {
                        "student_name" -> unlabelledDetector.isValidStudentName(cleanValue)
                        "enrollment_number" -> cleanValue.matches(Regex("""^\d{6,18}$""")) || (cleanValue.length in 6..20 && cleanValue.any { it.isDigit() })
                        "roll_number" -> cleanValue.matches(Regex("""^[A-Za-z0-9\-_]{1,12}$""")) && !unlabelledDetector.isCodeOrTechnicalTerm(cleanValue)
                        else -> cleanValue.matches(Regex("""^[A-Za-z0-9\-_/]{3,20}$""")) && cleanValue.any { it.isDigit() } && !unlabelledDetector.isCodeOrTechnicalTerm(cleanValue)
                    }

                    if (isValid) {
                        matchedBlocks.add(block.text)

                        val replVal = getProfileReplacement(detectedFieldType, savedProfile)

                        candidates.add(
                            DetectionCandidate(
                                id = UUID.randomUUID().toString(),
                                fieldType = detectedFieldType,
                                detectedText = cleanValue,
                                replacementText = replVal,
                                confidence = 0.95f,
                                pageIndex = pageIndex,
                                normalizedBox = block.bbox.map { it.toInt() },
                                pdfPointBox = block.rawBbox,
                                fontName = block.fontName,
                                fontSize = block.fontSize,
                                pairId = null,
                                requiresConfirmation = false,
                                isOcr = page.isScanned
                            )
                        )
                    }
                }
            }
        }

        // --- PASS 2: Page-by-Page Adaptive Footer Unlabelled Pair Detection ---
        for (page in extractedData.pages) {
            val pageIndex = page.pageNumber - 1
            val pageHeight = page.height
            val matchedBlocks = matchedBlocksByPage.getOrPut(pageIndex) { mutableSetOf() }

            val pageVerif = docVerification.pageResults.getOrNull(pageIndex)
            val pageFooterStatus = pageVerif?.status ?: FooterStatus.FOOTER_NOT_FOUND

            // Adaptive footer zone: use verified boundary, or separator line, or bottom 30% of page
            val footerBoundaryY = when {
                pageVerif?.hasSeparatorLine == true && pageVerif.separatorY != null -> pageVerif.separatorY - 5f
                pageVerif != null && pageVerif.boundaryY < pageHeight * 0.95f -> pageVerif.boundaryY - 10f
                else -> pageHeight * 0.70f
            }

            // Unlabelled identity pair detection in footer zone
            val footerZoneBlocks = page.blocks.filter { block ->
                !matchedBlocks.contains(block.text) && block.rawBbox[1] >= footerBoundaryY
            }

            val unlabelledPairs = unlabelledDetector.detectUnlabelledPairs(footerZoneBlocks)

            for (pair in unlabelledPairs) {
                matchedBlocks.add(pair.nameBlock.text)
                matchedBlocks.add(pair.idBlock.text)

                val isUncertain = (pageFooterStatus == FooterStatus.FOOTER_UNCERTAIN)
                val baseConf = if (isUncertain) minOf(0.75f, pair.confidence) else pair.confidence
                val requireConfirm = isUncertain || baseConf < 0.85f

                // Student Name candidate
                candidates.add(
                    DetectionCandidate(
                        id = UUID.randomUUID().toString(),
                        fieldType = "student_name",
                        detectedText = pair.name,
                        replacementText = getProfileReplacement("student_name", savedProfile),
                        confidence = baseConf,
                        pageIndex = pageIndex,
                        normalizedBox = pair.nameBlock.bbox.map { it.toInt() },
                        pdfPointBox = pair.nameBlock.rawBbox,
                        fontName = pair.nameBlock.fontName,
                        fontSize = pair.nameBlock.fontSize,
                        pairId = pair.pairId,
                        requiresConfirmation = requireConfirm,
                        isOcr = page.isScanned
                    )
                )

                // Identifier candidate
                val replId = getProfileReplacement(pair.identifierType, savedProfile)

                candidates.add(
                    DetectionCandidate(
                        id = UUID.randomUUID().toString(),
                        fieldType = pair.identifierType,
                        detectedText = pair.identifier,
                        replacementText = replId,
                        confidence = baseConf,
                        pageIndex = pageIndex,
                        normalizedBox = pair.idBlock.bbox.map { it.toInt() },
                        pdfPointBox = pair.idBlock.rawBbox,
                        fontName = pair.idBlock.fontName,
                        fontSize = pair.idBlock.fontSize,
                        pairId = pair.pairId,
                        requiresConfirmation = requireConfirm,
                        isOcr = page.isScanned
                    )
                )
            }

            // Also check for standalone unlabelled single identity blocks in footer
            for (block in footerZoneBlocks) {
                if (matchedBlocks.contains(block.text)) continue
                val clean = cleanExtractedValue(block.text)
                if (clean.isBlank()) continue

                if (unlabelledDetector.isValidStudentName(clean)) {
                    matchedBlocks.add(block.text)
                    candidates.add(
                        DetectionCandidate(
                            id = UUID.randomUUID().toString(),
                            fieldType = "student_name",
                            detectedText = clean,
                            replacementText = getProfileReplacement("student_name", savedProfile),
                            confidence = 0.88f,
                            pageIndex = pageIndex,
                            normalizedBox = block.bbox.map { it.toInt() },
                            pdfPointBox = block.rawBbox,
                            fontName = block.fontName,
                            fontSize = block.fontSize,
                            pairId = null,
                            requiresConfirmation = false,
                            isOcr = page.isScanned
                        )
                    )
                } else {
                    val idType = unlabelledDetector.classifyIdentifier(clean)
                    if (idType != null) {
                        matchedBlocks.add(block.text)
                        val replId = getProfileReplacement(idType, savedProfile)
                        candidates.add(
                            DetectionCandidate(
                                id = UUID.randomUUID().toString(),
                                fieldType = idType,
                                detectedText = clean,
                                replacementText = replId,
                                confidence = 0.88f,
                                pageIndex = pageIndex,
                                normalizedBox = block.bbox.map { it.toInt() },
                                pdfPointBox = block.rawBbox,
                                fontName = block.fontName,
                                fontSize = block.fontSize,
                                pairId = null,
                                requiresConfirmation = false,
                                isOcr = page.isScanned
                            )
                        )
                    }
                }
            }

            // --- PASS 3: Layout / ONNX inference on remaining footer blocks ---
            val remainingBlocks = footerZoneBlocks.filter { !matchedBlocks.contains(it.text) }
            if (remainingBlocks.isNotEmpty()) {
                val tokens = remainingBlocks.map { it.text }
                val bboxes = remainingBlocks.map { b -> b.bbox.map { it.toInt() } }

                val layoutEntities = onnxService.predictPage(tokens, bboxes, pageHeight)

                for (entity in layoutEntities) {
                    if (entity.entityType in listOf("footer_region", "page_number", "o")) {
                        continue
                    }

                    val firstTokenIdx = entity.tokenIndices.firstOrNull() ?: 0
                    val sourceBlock = remainingBlocks.getOrNull(firstTokenIdx) ?: remainingBlocks[0]
                    matchedBlocks.add(sourceBlock.text)

                    val replVal = getProfileReplacement(entity.entityType, savedProfile)

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
                            requiresConfirmation = isUncertain || finalConf < 0.85f,
                            isOcr = page.isScanned
                        )
                    )
                }
            }
        }

        // --- PASS 4: Document-Wide Multi-Page Identity Propagation ---
        // Collect verified student credentials from passes 1-3
        val verifiedNames = candidates
            .filter { it.fieldType == "student_name" && it.confidence >= 0.80f }
            .map { it.detectedText.trim() }
            .filter { unlabelledDetector.isValidStudentName(it) }
            .distinct()

        val verifiedEnrollments = candidates
            .filter { it.fieldType == "enrollment_number" && it.confidence >= 0.80f }
            .map { it.detectedText.trim() }
            .distinct()

        val verifiedRolls = candidates
            .filter { it.fieldType == "roll_number" && it.confidence >= 0.80f }
            .map { it.detectedText.trim() }
            .distinct()

        for (page in extractedData.pages) {
            val pageIndex = page.pageNumber - 1
            val pageCandidates = candidates.filter { it.pageIndex == pageIndex }

            for (knownName in verifiedNames) {
                val hasNameOnPage = pageCandidates.any { it.fieldType == "student_name" && it.detectedText.equals(knownName, ignoreCase = true) }
                if (!hasNameOnPage) {
                    // Search all blocks on this page for known student name
                    val matchingBlock = page.blocks.firstOrNull { block ->
                        val text = block.text.trim()
                        !isProseSentence(text) &&
                        (text.equals(knownName, ignoreCase = true) ||
                         text.contains(knownName, ignoreCase = true) && !unlabelledDetector.isAcademicTerm(text))
                    }

                    if (matchingBlock != null) {
                        candidates.add(
                            DetectionCandidate(
                                id = UUID.randomUUID().toString(),
                                fieldType = "student_name",
                                detectedText = knownName,
                                replacementText = getProfileReplacement("student_name", savedProfile),
                                confidence = 0.92f,
                                pageIndex = pageIndex,
                                normalizedBox = matchingBlock.bbox.map { it.toInt() },
                                pdfPointBox = matchingBlock.rawBbox,
                                fontName = matchingBlock.fontName,
                                fontSize = matchingBlock.fontSize,
                                pairId = null,
                                requiresConfirmation = false,
                                isOcr = page.isScanned
                            )
                        )
                    }
                }
            }

            for (knownEnrollment in verifiedEnrollments) {
                val hasEnrollOnPage = pageCandidates.any { it.fieldType == "enrollment_number" && it.detectedText.equals(knownEnrollment, ignoreCase = true) }
                if (!hasEnrollOnPage) {
                    val matchingBlock = page.blocks.firstOrNull { block ->
                        val text = block.text.trim()
                        !isProseSentence(text) &&
                        (text.equals(knownEnrollment, ignoreCase = true) ||
                         text.contains(knownEnrollment, ignoreCase = true) && !unlabelledDetector.isPageNumberText(text))
                    }

                    if (matchingBlock != null) {
                        candidates.add(
                            DetectionCandidate(
                                id = UUID.randomUUID().toString(),
                                fieldType = "enrollment_number",
                                detectedText = knownEnrollment,
                                replacementText = getProfileReplacement("enrollment_number", savedProfile),
                                confidence = 0.92f,
                                pageIndex = pageIndex,
                                normalizedBox = matchingBlock.bbox.map { it.toInt() },
                                pdfPointBox = matchingBlock.rawBbox,
                                fontName = matchingBlock.fontName,
                                fontSize = matchingBlock.fontSize,
                                pairId = null,
                                requiresConfirmation = false,
                                isOcr = page.isScanned
                            )
                        )
                    }
                }
            }

            for (knownRoll in verifiedRolls) {
                val hasRollOnPage = pageCandidates.any { it.fieldType == "roll_number" && it.detectedText.equals(knownRoll, ignoreCase = true) }
                if (!hasRollOnPage) {
                    val matchingBlock = page.blocks.firstOrNull { block ->
                        val text = block.text.trim()
                        !isProseSentence(text) &&
                        text.equals(knownRoll, ignoreCase = true)
                    }

                    if (matchingBlock != null) {
                        candidates.add(
                            DetectionCandidate(
                                id = UUID.randomUUID().toString(),
                                fieldType = "roll_number",
                                detectedText = knownRoll,
                                replacementText = getProfileReplacement("roll_number", savedProfile),
                                confidence = 0.90f,
                                pageIndex = pageIndex,
                                normalizedBox = matchingBlock.bbox.map { it.toInt() },
                                pdfPointBox = matchingBlock.rawBbox,
                                fontName = matchingBlock.fontName,
                                fontSize = matchingBlock.fontSize,
                                pairId = null,
                                requiresConfirmation = false,
                                isOcr = page.isScanned
                            )
                        )
                    }
                }
            }
        }

        // Link any unlinked name and identifier candidates sharing the same footer line into a unified pair
        linkFooterPairs(candidates)

        return OrchestrationResult(
            candidates = candidates,
            footerVerification = docVerification
        )
    }

    private fun cleanExtractedValue(value: String): String {
        return value.trim(' ', ':', '-', '–', '—', '|', ',', ';', '(', ')', '[', ']', '{', '}')
    }

    private fun isProseSentence(text: String): Boolean {
        val proseMatches = FooterRegionDetector.RE_PROSE_WORDS.findAll(text).count()
        return proseMatches >= 3 || (text.split(Regex("""\s+""")).size > 12 && text.endsWith("."))
    }

    private fun linkFooterPairs(candidates: MutableList<DetectionCandidate>) {
        val byPage = candidates.groupBy { it.pageIndex }
        for ((_, pageCands) in byPage) {
            val names = pageCands.filter { it.fieldType == "student_name" && it.pairId == null }
            val ids = pageCands.filter { it.fieldType in listOf("enrollment_number", "roll_number", "student_id") && it.pairId == null }

            for (nameCand in names) {
                val matchingId = ids.firstOrNull { idCand ->
                    // Check if on same horizontal baseline (y0 within 6pt)
                    val yDiff = kotlin.math.abs(nameCand.pdfPointBox[1] - idCand.pdfPointBox[1])
                    yDiff <= 6.0f
                }
                if (matchingId != null) {
                    val sharedPairId = "pair_${UUID.randomUUID().toString().take(8)}"
                    val nameIdx = candidates.indexOfFirst { it.id == nameCand.id }
                    val idIdx = candidates.indexOfFirst { it.id == matchingId.id }
                    if (nameIdx >= 0) candidates[nameIdx] = candidates[nameIdx].copy(pairId = sharedPairId)
                    if (idIdx >= 0) candidates[idIdx] = candidates[idIdx].copy(pairId = sharedPairId)
                }
            }
        }
    }
}
