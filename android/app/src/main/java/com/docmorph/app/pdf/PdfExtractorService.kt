package com.docmorph.app.pdf

import android.content.Context
import com.docmorph.app.db.AppDatabase
import com.docmorph.app.ocr.OfflineOcrService
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import com.tom_roush.pdfbox.text.TextPosition
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.OutputStreamWriter
import java.io.Writer
import kotlin.math.max
import kotlin.math.min

data class NativeTextBlock(
    val text: String,
    val bbox: List<Float>, // [x0, y0, x1, y1] normalized to [0, 1000]
    val rawBbox: List<Float>, // [x0, y0, x1, y1] in PDF points
    val fontName: String? = null,
    val fontSize: Float = 0f
)

data class NativePageResult(
    val pageNumber: Int,
    val width: Float,
    val height: Float,
    val isScanned: Boolean,
    val blocks: List<NativeTextBlock>
)

data class ExtractionResult(
    val documentId: String,
    val totalPages: Int,
    val isScanned: Boolean,
    val pages: List<NativePageResult>
)

class PdfExtractorService(private val context: Context) {

    private val db = AppDatabase.getDatabase(context)
    private val ocrService = OfflineOcrService(context)

    init {
        PDFBoxResourceLoader.init(context.applicationContext)
    }

    suspend fun extractDocument(documentId: String, filePath: String): ExtractionResult = withContext(Dispatchers.IO) {
        val file = File(filePath)
        if (!file.exists()) {
            throw IllegalArgumentException("File does not exist at $filePath")
        }

        var anyPageScanned = false
        val pageResults = mutableListOf<NativePageResult>()

        PDDocument.load(file).use { doc ->
            val pageCount = doc.numberOfPages

            for (pageIndex in 0 until pageCount) {
                val page = doc.getPage(pageIndex)
                val mediaBox = page.mediaBox
                val cropBox = page.cropBox ?: mediaBox
                val rotation = page.rotation

                val isRotated90or270 = (rotation == 90 || rotation == 270)
                val pageWidth = if (isRotated90or270) cropBox.height else cropBox.width
                val pageHeight = if (isRotated90or270) cropBox.width else cropBox.height

                // Extract text positions using custom PDFTextStripper
                val extractor = CoordinateStripper(pageWidth, pageHeight)
                extractor.startPage = pageIndex + 1
                extractor.endPage = pageIndex + 1
                extractor.getText(doc)

                val extractedBlocks = extractor.lineBlocks

                if (extractedBlocks.isEmpty() || extractor.totalCharCount < 10) {
                    // Page has no selectable text -> fallback to offline bundled OCR
                    val ocrResult = ocrService.ocrPage(file, pageIndex)
                    val ocrMappedBlocks = ocrResult.blocks.map { block ->
                        NativeTextBlock(
                            text = block.text,
                            bbox = block.bbox,
                            rawBbox = listOf(
                                (block.bbox[0] / 1000f) * pageWidth,
                                (block.bbox[1] / 1000f) * pageHeight,
                                (block.bbox[2] / 1000f) * pageWidth,
                                (block.bbox[3] / 1000f) * pageHeight
                            ),
                            fontName = "OCR",
                            fontSize = 12f
                        )
                    }

                    anyPageScanned = true
                    pageResults.add(
                        NativePageResult(
                            pageNumber = pageIndex + 1,
                            width = pageWidth,
                            height = pageHeight,
                            isScanned = true,
                            blocks = ocrMappedBlocks
                        )
                    )
                } else {
                    pageResults.add(
                        NativePageResult(
                            pageNumber = pageIndex + 1,
                            width = pageWidth,
                            height = pageHeight,
                            isScanned = false,
                            blocks = extractedBlocks
                        )
                    )
                }
            }
        }

        // Update document entity in Room DB
        val existing = db.documentDao().getDocumentById(documentId)
        if (existing != null) {
            db.documentDao().updateDocument(
                existing.copy(
                    isScanned = anyPageScanned,
                    status = "EXTRACTED",
                    updatedAt = System.currentTimeMillis()
                )
            )
        }

        ExtractionResult(
            documentId = documentId,
            totalPages = pageResults.size,
            isScanned = anyPageScanned,
            pages = pageResults
        )
    }

    /**
     * Line-level bounding box text stripper for PDFBox
     */
    private class CoordinateStripper(
        private val pageWidth: Float,
        private val pageHeight: Float
    ) : PDFTextStripper() {

        val lineBlocks = mutableListOf<NativeTextBlock>()
        var totalCharCount = 0

        private var currentLine = StringBuilder()
        private var lineX0 = Float.MAX_VALUE
        private var lineY0 = Float.MAX_VALUE
        private var lineX1 = Float.MIN_VALUE
        private var lineY1 = Float.MIN_VALUE
        private var currentFontName: String? = null
        private var currentFontSize = 0f

        init {
            sortByPosition = true
            output = OutputStreamWriter(ByteArrayOutputStream())
        }

        override fun writeString(text: String, textPositions: List<TextPosition>) {
            if (textPositions.isEmpty()) return

            currentLine.clear()
            lineX0 = Float.MAX_VALUE
            lineY0 = Float.MAX_VALUE
            lineX1 = Float.MIN_VALUE
            lineY1 = Float.MIN_VALUE

            for (pos in textPositions) {
                totalCharCount++
                currentLine.append(pos.unicode)

                val x = pos.xDirAdj
                val y = pos.yDirAdj
                val w = pos.widthDirAdj
                val h = pos.heightDir

                lineX0 = min(lineX0, x)
                lineY0 = min(lineY0, y - h)
                lineX1 = max(lineX1, x + w)
                lineY1 = max(lineY1, y)

                currentFontName = pos.font?.name
                currentFontSize = pos.fontSizeInPt
            }

            val lineText = currentLine.toString().trim()
            if (lineText.isNotEmpty()) {
                val normX0 = (lineX0 / pageWidth) * 1000f
                val normY0 = (lineY0 / pageHeight) * 1000f
                val normX1 = (lineX1 / pageWidth) * 1000f
                val normY1 = (lineY1 / pageHeight) * 1000f

                lineBlocks.add(
                    NativeTextBlock(
                        text = lineText,
                        bbox = listOf(
                            normX0.coerceIn(0f, 1000f),
                            normY0.coerceIn(0f, 1000f),
                            normX1.coerceIn(0f, 1000f),
                            normY1.coerceIn(0f, 1000f)
                        ),
                        rawBbox = listOf(lineX0, lineY0, lineX1, lineY1),
                        fontName = currentFontName,
                        fontSize = currentFontSize
                    )
                )
            }
        }
    }
}

