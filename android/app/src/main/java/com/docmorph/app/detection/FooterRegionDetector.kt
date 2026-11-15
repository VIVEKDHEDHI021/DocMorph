package com.docmorph.app.detection

import com.docmorph.app.pdf.NativeTextBlock
import java.io.File

data class FooterBoundaryResult(
    val boundaryY: Float,
    val hasDividerLine: Boolean,
    val dividerY: Float? = null
)

class FooterRegionDetector {

    /**
     * Detects the footer boundary Y coordinate.
     * Evaluates horizontal line dividers and whitespace gap analysis in the lower 40% of the page,
     * with fallback to a default 20% footer ratio.
     */
    fun detectFooterBoundary(
        pdfFile: File,
        pageIndex: Int,
        pageHeight: Float,
        blocks: List<NativeTextBlock>
    ): FooterBoundaryResult {
        // 1. Check for horizontal divider-like text blocks (e.g. repeated dashes, underscores, rules)
        val lowerThreshold = pageHeight * 0.60f
        val ruleBlocks = blocks.filter { block ->
            block.rawBbox[1] >= lowerThreshold &&
            (block.text.matches(Regex("""^[-_—–.]{10,}$""")) || (block.rawBbox[2] - block.rawBbox[0] >= 150f && (block.rawBbox[3] - block.rawBbox[1]) <= 3.0f))
        }

        if (ruleBlocks.isNotEmpty()) {
            val dividerY = ruleBlocks.minOf { it.rawBbox[1] }
            return FooterBoundaryResult(
                boundaryY = dividerY,
                hasDividerLine = true,
                dividerY = dividerY
            )
        }

        // 2. Adaptive whitespace gap detection in the lower 35% of the page
        val gapLowerThreshold = pageHeight * 0.65f
        val footerBlocks = blocks.filter { it.rawBbox[1] >= gapLowerThreshold }
            .sortedBy { it.rawBbox[1] }

        if (footerBlocks.size >= 2) {
            var largestGap = 0f
            var gapBoundaryY = 0f

            for (i in 0 until footerBlocks.size - 1) {
                val currentBottom = footerBlocks[i].rawBbox[3]
                val nextTop = footerBlocks[i + 1].rawBbox[1]
                val gap = nextTop - currentBottom
                if (gap > 20f && gap > largestGap) {
                    largestGap = gap
                    gapBoundaryY = currentBottom + (gap / 2.0f)
                }
            }

            if (largestGap >= 20f && gapBoundaryY > 0f) {
                return FooterBoundaryResult(
                    boundaryY = gapBoundaryY,
                    hasDividerLine = false,
                    dividerY = null
                )
            }
        }

        // 3. Fallback to standard 20% page ratio
        val defaultBoundaryY = pageHeight * 0.80f
        return FooterBoundaryResult(
            boundaryY = defaultBoundaryY,
            hasDividerLine = false,
            dividerY = null
        )
    }
}
