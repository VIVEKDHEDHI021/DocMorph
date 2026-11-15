package com.docmorph.app.detection

enum class FooterStatus {
    FOOTER_CONFIRMED,
    FOOTER_NOT_FOUND,
    FOOTER_UNCERTAIN,
    DOCUMENT_UNREADABLE
}

data class FooterEvidenceScores(
    val layoutScore: Float = 0f,
    val multiPageScore: Float = 0f,
    val semanticScore: Float = 0f,
    val negativeScore: Float = 0f,
    val totalScore: Float = 0f
)

data class PageFooterVerification(
    val pageNumber: Int,
    val status: FooterStatus,
    val confidence: Float,
    val boundaryY: Float,
    val hasSeparatorLine: Boolean = false,
    val separatorY: Float? = null,
    val evidence: FooterEvidenceScores = FooterEvidenceScores(),
    val negativeReasons: List<String> = emptyList(),
    val candidateTexts: List<String> = emptyList()
)

data class DocumentFooterVerification(
    val status: FooterStatus,
    val confidence: Float,
    val totalPages: Int,
    val confirmedPagesCount: Int = 0,
    val uncertainPagesCount: Int = 0,
    val notFoundPagesCount: Int = 0,
    val pageResults: List<PageFooterVerification> = emptyList(),
    val summaryMessage: String = ""
)
