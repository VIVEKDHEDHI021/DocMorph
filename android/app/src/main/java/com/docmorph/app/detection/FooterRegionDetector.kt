package com.docmorph.app.detection

import com.docmorph.app.pdf.NativeTextBlock
import java.io.File
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

data class FooterBoundaryResult(
    val boundaryY: Float,
    val hasDividerLine: Boolean,
    val dividerY: Float? = null,
    val status: FooterStatus = FooterStatus.FOOTER_NOT_FOUND,
    val confidence: Float = 0f
)

class FooterRegionDetector {

    companion object {
        val NEGATIVE_KEYWORDS = setOf(
            "conclusion", "conclusions", "result", "results", "observation", "observations",
            "apparatus", "theory", "procedure", "precaution", "precautions",
            "experiment", "practical", "exercise", "assignment", "problem", "solution",
            "chapter", "section", "unit", "module", "topic", "index",
            "reference", "references", "bibliography", "citation", "citations",
            "department", "faculty", "university", "institute", "college",
            "author", "authors", "edition", "editions", "published", "publisher", "isbn", "issn",
            "syllabus", "curriculum", "aim", "objective", "discussion",
            "figure", "fig.", "table", "chart", "diagram", "graph",
            "algorithm", "code", "output", "program", "source code",
            "course", "subject", "signature", "remark", "grade", "assessment"
        )

        val RE_EXP_CHAPTER = Regex("""(?i)\b(?:experiment|exp\.?|practical|chapter|unit|section|exercise)\s*(?:no\.?|#)?\s*\d+""")
        val RE_SOLITARY_PAGE_NUMBER = Regex("""(?i)^(?:page\s*\d+(\s*of\s*\d+)?|\d+\s*/\s*\d+|[-–—]\s*\d+\s*[-–—]|\d{1,3})$""")
        val RE_PROSE_WORDS = Regex("""(?i)\b(?:the|this|that|which|these|those|with|from|between|because|therefore|however|where|when|should|would|could)\b""")
    }

    /**
     * Backward-compatible boundary detector enhanced with verification status.
     */
    fun detectFooterBoundary(
        pdfFile: File,
        pageIndex: Int,
        pageHeight: Float,
        blocks: List<NativeTextBlock>
    ): FooterBoundaryResult {
        val pageVerif = verifyPage(
            pageIndex = pageIndex,
            pageHeight = pageHeight,
            pageWidth = 612f,
            blocks = blocks
        )

        return FooterBoundaryResult(
            boundaryY = pageVerif.boundaryY,
            hasDividerLine = pageVerif.hasSeparatorLine,
            dividerY = pageVerif.separatorY,
            status = pageVerif.status,
            confidence = pageVerif.confidence
        )
    }

    /**
     * Multi-signal verification of an individual page's footer zone.
     */
    fun verifyPage(
        pageIndex: Int,
        pageHeight: Float,
        pageWidth: Float,
        blocks: List<NativeTextBlock>
    ): PageFooterVerification {
        val lowerThreshold = pageHeight * 0.70f

        // 1. Check for horizontal divider-like text blocks (rules/lines)
        val ruleBlocks = blocks.filter { block ->
            block.rawBbox[1] >= (pageHeight * 0.60f) &&
            (block.text.matches(Regex("""^[-_—–.]{8,}$""")) ||
             (block.rawBbox[2] - block.rawBbox[0] >= 150f && (block.rawBbox[3] - block.rawBbox[1]) <= 3.0f))
        }

        val hasDivider = ruleBlocks.isNotEmpty()
        val dividerY = if (hasDivider) ruleBlocks.minOf { it.rawBbox[1] } else null

        val candidateThreshold = dividerY ?: lowerThreshold
        val bodyLines = blocks.filter { it.rawBbox[3] < candidateThreshold }
        val footerCandidates = blocks.filter { it.rawBbox[1] >= candidateThreshold }

        if (footerCandidates.isEmpty()) {
            return PageFooterVerification(
                pageNumber = pageIndex + 1,
                status = FooterStatus.FOOTER_NOT_FOUND,
                confidence = 0.95f,
                boundaryY = pageHeight,
                hasSeparatorLine = false,
                separatorY = null,
                negativeReasons = listOf("No text in lower page region"),
                candidateTexts = emptyList()
            )
        }

        var layoutScore = 0f
        var semanticScore = 0f
        var negativeScore = 0f
        val negativeReasons = mutableListOf<String>()

        val candidateTexts = footerCandidates.map { it.text.trim() }.filter { it.isNotEmpty() }
        val combinedFooterText = candidateTexts.joinToString(" ")
        val combinedLower = combinedFooterText.lowercase()

        // --- A. Negative Evidence Checks ---
        for (cand in candidateTexts) {
            val textLower = cand.lowercase()
            for (kw in NEGATIVE_KEYWORDS) {
                if (Regex("""\b${Regex.escape(kw)}\b""").containsMatchIn(textLower)) {
                    negativeScore += 35f
                    negativeReasons.add("Contains negative body keyword '$kw'")
                    break
                }
            }

            if (RE_EXP_CHAPTER.containsMatchIn(cand)) {
                negativeScore += 40f
                negativeReasons.add("Contains experiment/chapter pattern: '${cand.take(25)}'")
            }

            val proseCount = RE_PROSE_WORDS.findAll(cand).count()
            if (proseCount >= 3 || (cand.split(Regex("""\s+""")).size > 12 && cand.endsWith("."))) {
                negativeScore += 35f
                negativeReasons.add("Prose-like running sentence structure ($proseCount prose words)")
            }
        }

        // Solitary page number check
        if (candidateTexts.size == 1 && RE_SOLITARY_PAGE_NUMBER.matches(candidateTexts[0])) {
            negativeScore += 45f
            negativeReasons.add("Solitary page number alone (not a student footer)")
        }

        // Body text continuation (lack of vertical separation)
        if (bodyLines.isNotEmpty()) {
            val lowestBodyY = bodyLines.maxOf { it.rawBbox[3] }
            val highestFooterY = footerCandidates.minOf { it.rawBbox[1] }
            val gap = highestFooterY - lowestBodyY

            if (!hasDivider) {
                if (gap < 16f) {
                    negativeScore += 35f
                    negativeReasons.add("No vertical separation from body text (gap=${gap.toInt()}pt)")
                } else if (gap >= 28f) {
                    layoutScore += 25f
                } else if (gap >= 18f) {
                    layoutScore += 15f
                }
            }
        } else {
            layoutScore += 10f
        }

        // --- B. Layout Evidence Checks ---
        if (hasDivider) {
            layoutScore += 40f
        }

        if (footerCandidates.size in 1..2) {
            layoutScore += 20f
        } else if (footerCandidates.size >= 5) {
            negativeScore += 25f
            negativeReasons.add("Too many lines in footer region (${footerCandidates.size} lines)")
        }

        val firstCandY0 = footerCandidates.minOf { it.rawBbox[1] }
        if (firstCandY0 >= pageHeight * 0.85f) {
            layoutScore += 20f
        } else if (firstCandY0 >= pageHeight * 0.78f) {
            layoutScore += 10f
        }

        // --- C. Semantic Evidence Checks (Supporting Only) ---
        val hasIdPair = Regex("""([A-Za-z\s.'-]{3,35})\s*[\(\[]\s*(\d{6,18}|[A-Za-z0-9\-_]{5,20})\s*[\)\]]""").containsMatchIn(combinedFooterText) ||
                        Regex("""([A-Za-z\s.'-]{3,35})\s*[-–—|]\s*(\d{6,18})""").containsMatchIn(combinedFooterText)
        if (hasIdPair) {
            semanticScore += 45f
            // If explicit student pair is found in footer zone, reduce spurious negative score from adjacent body words
            negativeScore = max(0f, negativeScore - 30f)
        }

        val hasExplicitLabels = Regex("""(?i)\b(?:name|enrollment(?:\s*no\.?)?|roll(?:\s*no\.?)?|student\s*id)\s*:""").containsMatchIn(combinedFooterText)
        if (hasExplicitLabels) {
            semanticScore += 35f
            negativeScore = max(0f, negativeScore - 20f)
        }

        val netScore = (layoutScore + semanticScore) - negativeScore

        val status: FooterStatus
        val conf: Float
        if (hasIdPair || hasExplicitLabels) {
            status = if (netScore >= 35f) FooterStatus.FOOTER_CONFIRMED else FooterStatus.FOOTER_UNCERTAIN
            conf = min(0.98f, max(0.75f, netScore / 100f))
        } else if (negativeScore >= 40f) {
            status = FooterStatus.FOOTER_NOT_FOUND
            conf = max(0.85f, min(0.99f, negativeScore / 100f))
        } else if (netScore >= 50f && layoutScore >= 20f) {
            status = FooterStatus.FOOTER_CONFIRMED
            conf = min(0.98f, max(0.70f, netScore / 100f))
        } else if (netScore >= 20f && negativeScore < 30f) {
            status = FooterStatus.FOOTER_UNCERTAIN
            conf = 0.50f
        } else {
            status = FooterStatus.FOOTER_NOT_FOUND
            conf = max(0.75f, 1f - max(0f, netScore) / 100f)
        }

        val boundaryY = dividerY ?: firstCandY0

        return PageFooterVerification(
            pageNumber = pageIndex + 1,
            status = status,
            confidence = conf,
            boundaryY = boundaryY,
            hasSeparatorLine = hasDivider,
            separatorY = dividerY,
            evidence = FooterEvidenceScores(
                layoutScore = layoutScore,
                multiPageScore = 0f,
                semanticScore = semanticScore,
                negativeScore = negativeScore,
                totalScore = netScore
            ),
            negativeReasons = negativeReasons.distinct(),
            candidateTexts = candidateTexts
        )
    }

    /**
     * Cross-page multi-page verification aggregating all pages.
     */
    fun verifyDocument(
        totalPages: Int,
        pageHeights: List<Float>,
        pageWidths: List<Float>,
        pagesBlocks: List<List<NativeTextBlock>>
    ): DocumentFooterVerification {
        if (totalPages <= 0 || pagesBlocks.isEmpty()) {
            return DocumentFooterVerification(
                status = FooterStatus.DOCUMENT_UNREADABLE,
                confidence = 0f,
                totalPages = 0,
                summaryMessage = "The document has zero readable pages."
            )
        }

        val prelims = mutableListOf<PageFooterVerification>()
        for (i in 0 until totalPages) {
            val blocks = pagesBlocks.getOrElse(i) { emptyList() }
            val h = pageHeights.getOrElse(i) { 792f }
            val w = pageWidths.getOrElse(i) { 612f }
            prelims.add(verifyPage(i, h, w, blocks))
        }

        // Multi-page position consistency
        val validConfirmedPages = prelims.filter { it.status == FooterStatus.FOOTER_CONFIRMED || it.status == FooterStatus.FOOTER_UNCERTAIN }
        val finalPageResults = mutableListOf<PageFooterVerification>()

        for (p in prelims) {
            if (p.status == FooterStatus.FOOTER_CONFIRMED && totalPages >= 2) {
                // Adaptive multi-page matching: supports variable vertical offsets (up to 80pt) across pages
                val matchingCount = validConfirmedPages.count { other ->
                    abs(other.boundaryY - p.boundaryY) <= 80f ||
                    (p.candidateTexts.isNotEmpty() && other.candidateTexts.isNotEmpty() &&
                     other.candidateTexts.any { tc -> p.candidateTexts.any { pc -> tc.contains(pc) || pc.contains(tc) } })
                }
                val mpBonus = if (matchingCount >= 2) 20f else if (matchingCount >= 1) 10f else 0f
                val updatedEvidence = p.evidence.copy(
                    multiPageScore = mpBonus,
                    totalScore = p.evidence.totalScore + mpBonus
                )
                finalPageResults.add(p.copy(evidence = updatedEvidence))
            } else {
                finalPageResults.add(p)
            }
        }

        val confirmedCount = finalPageResults.count { it.status == FooterStatus.FOOTER_CONFIRMED }
        val uncertainCount = finalPageResults.count { it.status == FooterStatus.FOOTER_UNCERTAIN }
        val notFoundCount = finalPageResults.count { it.status == FooterStatus.FOOTER_NOT_FOUND }

        val docStatus: FooterStatus
        val docConf: Float
        val summaryMsg: String

        if (confirmedCount >= 1) {
            docStatus = FooterStatus.FOOTER_CONFIRMED
            docConf = finalPageResults.filter { it.status == FooterStatus.FOOTER_CONFIRMED }.map { it.confidence }.average().toFloat()
            summaryMsg = "A recognizable footer was confirmed on $confirmedCount of $totalPages page(s)."
        } else if (uncertainCount >= 1) {
            docStatus = FooterStatus.FOOTER_UNCERTAIN
            docConf = 0.50f
            summaryMsg = "Footer candidates exist but confidence is insufficient for automatic personalization."
        } else {
            docStatus = FooterStatus.FOOTER_NOT_FOUND
            docConf = 0.90f
            summaryMsg = "This document does not appear to contain a recognizable footer."
        }

        return DocumentFooterVerification(
            status = docStatus,
            confidence = docConf,
            totalPages = totalPages,
            confirmedPagesCount = confirmedCount,
            uncertainPagesCount = uncertainCount,
            notFoundPagesCount = notFoundCount,
            pageResults = finalPageResults,
            summaryMessage = summaryMsg
        )
    }
}
