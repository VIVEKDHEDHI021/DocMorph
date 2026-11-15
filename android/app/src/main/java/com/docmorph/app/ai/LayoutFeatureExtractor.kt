package com.docmorph.app.ai

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/**
 * 36-feature extractor matching ai_training/train.py LayoutFeatureExtractor with exact parity.
 */
object LayoutFeatureExtractor {

    private val NAME_KEYWORDS = setOf("name", "student", "candidate")
    private val ENR_KEYWORDS = setOf("enrollment", "enrolment", "enr", "reg", "registration")
    private val ROLL_KEYWORDS = setOf("roll", "rollno")
    private val PAGE_KEYWORDS = setOf("page", "of")

    /**
     * Extracts dense 36-dimensional feature vectors for tokens on a page.
     * Each bounding box must be [x0, y0, x1, y1] normalized to [0, 1000].
     */
    fun extractFeatures(
        tokens: List<String>,
        bboxes: List<List<Int>>
    ): Array<FloatArray> {
        val nTokens = tokens.size
        val features = Array(nTokens) { FloatArray(36) }

        for (i in 0 until nTokens) {
            val w = tokens[i]
            val bbox = bboxes[i]
            val x0 = bbox[0]
            val y0 = bbox[1]
            val x1 = bbox[2]
            val y1 = bbox[3]

            val wW = max(1, x1 - x0)
            val wH = max(1, y1 - y0)

            // 1. Spatial & Positional features (Normalized 0..1000 scale)
            val normX0 = x0 / 1000.0f
            val normY0 = y0 / 1000.0f
            val normX1 = x1 / 1000.0f
            val normY1 = y1 / 1000.0f
            val midX = (x0 + x1) / 2000.0f
            val midY = (y0 + y1) / 2000.0f
            val distBottom = max(0.0f, 1.0f - normY1)
            val distLeft = normX0
            val distRight = max(0.0f, 1.0f - normX1)
            val aspectRatio = min(10.0f, wW.toFloat() / max(1.0f, wH.toFloat()))

            // Binary spatial zone indicators
            val isBottomZone = if (y0 >= 850) 1.0f else 0.0f
            val isDeepFooter = if (y0 >= 900) 1.0f else 0.0f
            val isHeaderZone = if (y1 <= 150) 1.0f else 0.0f
            val isLeftAligned = if (x0 <= 150) 1.0f else 0.0f
            val isRightAligned = if (x1 >= 850) 1.0f else 0.0f
            val isCentered = if (abs(midX - 0.5f) <= 0.15f) 1.0f else 0.0f

            // 2. Text Lexical & Syntactic features
            val textLen = min(30, w.length)
            val cleanW = stripPunctuation(w)
            var digitsCount = 0
            var alphaCount = 0
            for (c in cleanW) {
                if (c.isDigit()) digitsCount++
                if (c.isLetter()) alphaCount++
            }
            val digitRatio = digitsCount.toFloat() / max(1, textLen)
            val alphaRatio = alphaCount.toFloat() / max(1, textLen)

            val isPureDigits = if (cleanW.isNotEmpty() && cleanW.all { it.isDigit() }) 1.0f else 0.0f
            val isPureAlpha = if (cleanW.isNotEmpty() && cleanW.all { it.isLetter() }) 1.0f else 0.0f
            val isTitleCase = if (isTitle(w)) 1.0f else 0.0f
            val isUpperCase = if (isUpper(w)) 1.0f else 0.0f
            val hasParens = if (w.contains('(') || w.contains(')') || w.contains('[') || w.contains(']')) 1.0f else 0.0f
            val hasDash = if (w.contains('-') || w.contains('–') || w.contains('|')) 1.0f else 0.0f

            val isEnrollmentLen = if (isPureDigits == 1.0f && cleanW.length in 9..15) 1.0f else 0.0f
            val isRollLen = if (isPureDigits == 1.0f && cleanW.length in 1..3) 1.0f else 0.0f
            val isPageNumCandidate = if (
                isPureDigits == 1.0f &&
                (cleanW.toIntOrNull() ?: Int.MAX_VALUE) <= 100 &&
                (x1 >= 800 || isCentered == 1.0f)
            ) 1.0f else 0.0f

            // 3. Contextual neighbor features (previous & next tokens)
            var prevYDiff = 0.0f
            var prevXDiff = 0.0f
            if (i > 0) {
                val prevB = bboxes[i - 1]
                prevYDiff = abs(y0 - prevB[1]) / 1000.0f
                prevXDiff = (x0 - prevB[2]) / 1000.0f
            }

            var nextYDiff = 0.0f
            var nextXDiff = 0.0f
            if (i < nTokens - 1) {
                val nextB = bboxes[i + 1]
                nextYDiff = abs(y0 - nextB[1]) / 1000.0f
                nextXDiff = (nextB[0] - x1) / 1000.0f
            }

            // Keyword contextual cues
            val wLower = cleanW.lowercase()
            val isNameKw = if (NAME_KEYWORDS.contains(wLower)) 1.0f else 0.0f
            val isEnrKw = if (ENR_KEYWORDS.contains(wLower)) 1.0f else 0.0f
            val isRollKw = if (ROLL_KEYWORDS.contains(wLower)) 1.0f else 0.0f
            val isPageKw = if (PAGE_KEYWORDS.contains(wLower)) 1.0f else 0.0f

            val row = features[i]
            row[0] = normX0
            row[1] = normY0
            row[2] = normX1
            row[3] = normY1
            row[4] = midX
            row[5] = midY
            row[6] = distBottom
            row[7] = distLeft
            row[8] = distRight
            row[9] = aspectRatio
            row[10] = isBottomZone
            row[11] = isDeepFooter
            row[12] = isHeaderZone
            row[13] = isLeftAligned
            row[14] = isRightAligned
            row[15] = isCentered
            row[16] = textLen / 30.0f
            row[17] = digitRatio
            row[18] = alphaRatio
            row[19] = isPureDigits
            row[20] = isPureAlpha
            row[21] = isTitleCase
            row[22] = isUpperCase
            row[23] = hasParens
            row[24] = hasDash
            row[25] = isEnrollmentLen
            row[26] = isRollLen
            row[27] = isPageNumCandidate
            row[28] = prevYDiff
            row[29] = prevXDiff
            row[30] = nextYDiff
            row[31] = nextXDiff
            row[32] = isNameKw
            row[33] = isEnrKw
            row[34] = isRollKw
            row[35] = isPageKw
        }

        return features
    }

    private fun stripPunctuation(str: String): String {
        val charsToStrip = setOf('(', ')', '[', ']', '-', '|', ',', '.', ':')
        var start = 0
        var end = str.length
        while (start < end && charsToStrip.contains(str[start])) {
            start++
        }
        while (end > start && charsToStrip.contains(str[end - 1])) {
            end--
        }
        return if (start >= end) "" else str.substring(start, end)
    }

    private fun isTitle(s: String): Boolean {
        if (s.isEmpty()) return false
        val words = s.split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (words.isEmpty()) return false
        return words.all { w ->
            val first = w[0]
            val rest = if (w.length > 1) w.substring(1) else ""
            (first.isLetter() && first.isUpperCase()) && (rest.isEmpty() || rest.all { !it.isLetter() || it.isLowerCase() })
        }
    }

    private fun isUpper(s: String): Boolean {
        val letters = s.filter { it.isLetter() }
        return letters.isNotEmpty() && letters.all { it.isUpperCase() }
    }
}

