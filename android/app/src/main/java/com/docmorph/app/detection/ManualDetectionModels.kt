package com.docmorph.app.detection

enum class SelectionType {
    AREA,
    TEXT
}

data class ManualSelectionInput(
    val documentId: String,
    val pageIndex: Int, // 0-based
    val selectionType: SelectionType,
    val rawBbox: List<Float>? = null, // [x0, y0, x1, y1] in points
    val normalizedBox: List<Int>? = null, // [x0, y0, x1, y1] in [0, 1000]
    val selectedText: String? = null,
    val pageWidth: Float,
    val pageHeight: Float
)

data class ManualDetectionResult(
    val documentId: String,
    val pageIndex: Int,
    val selectionType: SelectionType,
    val resolvedPdfBox: List<Float>,
    val extractedText: String,
    val footerStatus: FooterStatus,
    val confidence: Float,
    val candidates: List<DetectionCandidate>,
    val negativeReasons: List<String>,
    val summaryMessage: String
)
