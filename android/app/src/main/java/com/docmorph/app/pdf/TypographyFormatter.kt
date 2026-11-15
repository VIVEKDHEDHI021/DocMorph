package com.docmorph.app.pdf

import com.tom_roush.pdfbox.pdmodel.font.PDFont
import com.tom_roush.pdfbox.pdmodel.font.PDType1Font
import kotlin.math.max

data class FittedTypography(
    val font: PDFont,
    val fontSize: Float,
    val textWidth: Float,
    val hasOverflow: Boolean,
    val warningMessage: String? = null
)

class TypographyFormatter {

    companion object {
        const val MIN_FONT_SIZE = 6.0f
        const val DEFAULT_FONT_SIZE = 10.0f
    }

    /**
     * Maps an extracted font name or description to standard PDF Type-1 fonts.
     */
    fun resolveFont(fontName: String?): PDFont {
        val norm = fontName?.lowercase() ?: ""
        val isBold = norm.contains("bold") || norm.contains("black") || norm.contains("heavy") || norm.contains("medium")
        val isItalic = norm.contains("italic") || norm.contains("oblique")

        return when {
            norm.contains("times") || norm.contains("serif") || norm.contains("roman") || norm.contains("cambria") -> {
                when {
                    isBold && isItalic -> PDType1Font.TIMES_BOLD_ITALIC
                    isBold -> PDType1Font.TIMES_BOLD
                    isItalic -> PDType1Font.TIMES_ITALIC
                    else -> PDType1Font.TIMES_ROMAN
                }
            }
            norm.contains("courier") || norm.contains("mono") || norm.contains("consolas") -> {
                when {
                    isBold && isItalic -> PDType1Font.COURIER_BOLD_OBLIQUE
                    isBold -> PDType1Font.COURIER_BOLD
                    isItalic -> PDType1Font.COURIER_OBLIQUE
                    else -> PDType1Font.COURIER
                }
            }
            else -> {
                // Default Helvetica / Arial / Sans
                when {
                    isBold && isItalic -> PDType1Font.HELVETICA_BOLD_OBLIQUE
                    isBold -> PDType1Font.HELVETICA_BOLD
                    isItalic -> PDType1Font.HELVETICA_OBLIQUE
                    else -> PDType1Font.HELVETICA
                }
            }
        }
    }

    /**
     * Measures replacement string width and computes adaptive scaling down to 6.0pt
     * so that the text does not collide with adjacent page elements or overflow page boundaries.
     */
    fun calculateFittedFontSize(
        text: String,
        font: PDFont,
        baseFontSize: Float,
        availableWidth: Float
    ): FittedTypography {
        val effectiveBase = if (baseFontSize in MIN_FONT_SIZE..36.0f) baseFontSize else DEFAULT_FONT_SIZE
        val safeText = sanitizeAsciiText(text)

        val rawWidthAt1Pt: Float = try {
            font.getStringWidth(safeText) / 1000f
        } catch (_: Exception) {
            safeText.length * 0.52f
        }

        val currentWidth = rawWidthAt1Pt * effectiveBase

        if (availableWidth <= 0f || currentWidth <= availableWidth) {
            return FittedTypography(
                font = font,
                fontSize = effectiveBase,
                textWidth = currentWidth,
                hasOverflow = false,
                warningMessage = null
            )
        }

        // Calculate scaled font size
        val scale = availableWidth / currentWidth
        val calculatedSize = effectiveBase * scale

        return if (calculatedSize >= MIN_FONT_SIZE) {
            FittedTypography(
                font = font,
                fontSize = calculatedSize,
                textWidth = rawWidthAt1Pt * calculatedSize,
                hasOverflow = false,
                warningMessage = "Font scaled from ${effectiveBase}pt to ${"%.1f".format(calculatedSize)}pt to fit available width"
            )
        } else {
            FittedTypography(
                font = font,
                fontSize = MIN_FONT_SIZE,
                textWidth = rawWidthAt1Pt * MIN_FONT_SIZE,
                hasOverflow = true,
                warningMessage = "Text exceeds available width (${"%.1f".format(availableWidth)}pt) at minimum ${MIN_FONT_SIZE}pt font size"
            )
        }
    }

    /**
     * Sanitizes string to ensure compatibility with standard Type 1 font WinAnsiEncoding.
     */
    fun sanitizeAsciiText(text: String): String {
        return text
            .replace("–", "-")
            .replace("—", "-")
            .replace("’", "'")
            .replace("‘", "'")
            .replace("“", "\"")
            .replace("”", "\"")
            .replace("•", "*")
            .filter { it.code in 32..126 || it.code in 160..255 }
    }
}

