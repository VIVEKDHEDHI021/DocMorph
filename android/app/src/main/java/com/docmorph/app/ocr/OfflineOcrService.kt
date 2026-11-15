package com.docmorph.app.ocr

import android.content.Context
import android.graphics.Bitmap
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.math.min

data class OcrTextBlock(
    val text: String,
    val bbox: List<Float>, // [x0, y0, x1, y1] normalized to [0, 1000]
    val confidence: Float? = null
)

data class OcrPageResult(
    val pageNumber: Int,
    val width: Float,
    val height: Float,
    val blocks: List<OcrTextBlock>
)

class OfflineOcrService(private val context: Context) {

    // Bundled ML Kit Latin Text Recognizer - operates completely offline
    private val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)

    suspend fun ocrPage(pdfFile: File, pageIndex: Int): OcrPageResult = withContext(Dispatchers.IO) {
        var fileDescriptor: ParcelFileDescriptor? = null
        var pdfRenderer: PdfRenderer? = null
        var page: PdfRenderer.Page? = null
        var bitmap: Bitmap? = null

        try {
            fileDescriptor = ParcelFileDescriptor.open(pdfFile, ParcelFileDescriptor.MODE_READ_ONLY)
            pdfRenderer = PdfRenderer(fileDescriptor)

            if (pageIndex < 0 || pageIndex >= pdfRenderer.pageCount) {
                return@withContext OcrPageResult(pageIndex + 1, 0f, 0f, emptyList())
            }

            page = pdfRenderer.openPage(pageIndex)
            val pageWidth = page.width
            val pageHeight = page.height

            // Calculate scaled bitmap dimensions (target ~200 DPI or max dimension 2048 to prevent OOM)
            val scale = min(2.0f, 2048f / Math.max(pageWidth, pageHeight))
            val renderWidth = (pageWidth * scale).toInt()
            val renderHeight = (pageHeight * scale).toInt()

            bitmap = Bitmap.createBitmap(renderWidth, renderHeight, Bitmap.Config.ARGB_8888)
            // Render on white background
            bitmap.eraseColor(android.graphics.Color.WHITE)
            page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)

            val image = InputImage.fromBitmap(bitmap, 0)
            val visionText = recognizer.process(image).await()

            val blocks = mutableListOf<OcrTextBlock>()
            for (block in visionText.textBlocks) {
                for (line in block.lines) {
                    val box = line.boundingBox
                    if (box != null) {
                        // Normalize bounding box coordinates to [0, 1000] relative to bitmap width and height
                        val normX0 = (box.left.toFloat() / renderWidth.toFloat()) * 1000f
                        val normY0 = (box.top.toFloat() / renderHeight.toFloat()) * 1000f
                        val normX1 = (box.right.toFloat() / renderWidth.toFloat()) * 1000f
                        val normY1 = (box.bottom.toFloat() / renderHeight.toFloat()) * 1000f

                        blocks.add(
                            OcrTextBlock(
                                text = line.text,
                                bbox = listOf(normX0, normY0, normX1, normY1),
                                confidence = line.confidence
                            )
                        )
                    }
                }
            }

            OcrPageResult(
                pageNumber = pageIndex + 1,
                width = pageWidth.toFloat(),
                height = pageHeight.toFloat(),
                blocks = blocks
            )
        } finally {
            bitmap?.recycle()
            page?.close()
            pdfRenderer?.close()
            fileDescriptor?.close()
        }
    }
}

