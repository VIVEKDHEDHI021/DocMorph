package com.docmorph.app.storage

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import com.docmorph.app.db.AppDatabase
import com.docmorph.app.db.DocumentEntity
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.pdmodel.encryption.InvalidPasswordException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream
import java.util.UUID

class LocalPdfStorage(private val context: Context) {

    private val db = AppDatabase.getDatabase(context)
    private val originalsDir: File = File(context.filesDir, "originals").apply { if (!exists()) mkdirs() }
    private val personalizedDir: File = File(context.filesDir, "personalized").apply { if (!exists()) mkdirs() }

    init {
        PDFBoxResourceLoader.init(context.applicationContext)
    }

    data class ImportResult(
        val success: Boolean,
        val documentId: String? = null,
        val fileName: String? = null,
        val filePath: String? = null,
        val pageCount: Int = 0,
        val fileSizeBytes: Long = 0,
        val isEncrypted: Boolean = false,
        val errorMessage: String? = null
    )

    suspend fun importPdfFromUri(uri: Uri): ImportResult = withContext(Dispatchers.IO) {
        val documentId = UUID.randomUUID().toString()
        val originalFileName = queryFileName(uri) ?: "document_$documentId.pdf"
        val targetFile = File(originalsDir, "$documentId.pdf")

        try {
            // 1. Copy stream to private storage
            val stream: InputStream? = when (uri.scheme) {
                "file", null -> {
                    val p = uri.path ?: uri.toString()
                    File(p).inputStream()
                }
                else -> context.contentResolver.openInputStream(uri)
            }

            stream?.use { inputStream ->
                FileOutputStream(targetFile).use { outputStream ->
                    inputStream.copyTo(outputStream)
                }
            } ?: return@withContext ImportResult(
                success = false,
                errorMessage = "Failed to open input stream for selected file"
            )

            return@withContext validateAndSaveDocument(documentId, originalFileName, targetFile)
        } catch (e: Exception) {
            if (targetFile.exists()) targetFile.delete()
            return@withContext ImportResult(
                success = false,
                errorMessage = "Import error: ${e.message}"
            )
        }
    }

    suspend fun importPdfFromBytes(originalFileName: String, bytes: ByteArray): ImportResult = withContext(Dispatchers.IO) {
        val documentId = UUID.randomUUID().toString()
        val targetFile = File(originalsDir, "$documentId.pdf")

        try {
            FileOutputStream(targetFile).use { it.write(bytes) }
            return@withContext validateAndSaveDocument(documentId, originalFileName, targetFile)
        } catch (e: Exception) {
            if (targetFile.exists()) targetFile.delete()
            return@withContext ImportResult(
                success = false,
                errorMessage = "Import error: ${e.message}"
            )
        }
    }

    private suspend fun validateAndSaveDocument(documentId: String, originalFileName: String, targetFile: File): ImportResult {
        val fileSizeBytes = targetFile.length()

        // 2. Validate file size <= 20MB
        val maxSizeBytes = 20L * 1024 * 1024
        if (fileSizeBytes > maxSizeBytes) {
            targetFile.delete()
            return ImportResult(
                success = false,
                errorMessage = "File size exceeds 20MB limit (${fileSizeBytes / (1024 * 1024)}MB)"
            )
        }

        // 3. Validate PDF magic bytes (%PDF-)
        val headerBytes = ByteArray(5)
        targetFile.inputStream().use { it.read(headerBytes) }
        val headerString = String(headerBytes)
        if (!headerString.startsWith("%PDF-")) {
            targetFile.delete()
            return ImportResult(
                success = false,
                errorMessage = "Invalid PDF format: Missing %PDF- header"
            )
        }

        // 4. Validate with PDFBox and check encryption & page count
        var pageCount = 0
        var isEncrypted = false

        try {
            PDDocument.load(targetFile).use { doc ->
                if (doc.isEncrypted) {
                    isEncrypted = true
                } else {
                    pageCount = doc.numberOfPages
                }
            }
        } catch (e: InvalidPasswordException) {
            targetFile.delete()
            return ImportResult(
                success = false,
                isEncrypted = true,
                errorMessage = "Password protected PDFs are not supported"
            )
        } catch (e: Exception) {
            targetFile.delete()
            return ImportResult(
                success = false,
                errorMessage = "Failed to parse PDF document: ${e.message}"
            )
        }

        if (isEncrypted) {
            targetFile.delete()
            return ImportResult(
                success = false,
                isEncrypted = true,
                errorMessage = "Password protected PDFs are not supported"
            )
        }

        if (pageCount == 0) {
            targetFile.delete()
            return ImportResult(
                success = false,
                errorMessage = "PDF contains 0 pages or is corrupted"
            )
        }

        // 5. Store metadata in Room
        val entity = DocumentEntity(
            documentId = documentId,
            fileName = originalFileName,
            originalPath = targetFile.absolutePath,
            personalizedPath = null,
            pageCount = pageCount,
            isScanned = false,
            fileSizeBytes = fileSizeBytes,
            status = "IMPORTED"
        )
        db.documentDao().insertDocument(entity)

        return ImportResult(
            success = true,
            documentId = documentId,
            fileName = originalFileName,
            filePath = targetFile.absolutePath,
            pageCount = pageCount,
            fileSizeBytes = fileSizeBytes,
            isEncrypted = false
        )
    }

    suspend fun deleteDocument(documentId: String): Boolean = withContext(Dispatchers.IO) {
        val originalFile = File(originalsDir, "$documentId.pdf")
        if (originalFile.exists()) originalFile.delete()

        val personalizedFile = File(personalizedDir, "${documentId}_personalized.pdf")
        if (personalizedFile.exists()) personalizedFile.delete()

        db.documentDao().deleteDocumentById(documentId)
        true
    }

    suspend fun getDocument(documentId: String): DocumentEntity? = withContext(Dispatchers.IO) {
        db.documentDao().getDocumentById(documentId)
    }

    suspend fun getAllDocuments(): List<DocumentEntity> = withContext(Dispatchers.IO) {
        db.documentDao().getAllDocuments()
    }

    suspend fun exportToPublicDownloads(documentId: String, exportFileName: String? = null): String = withContext(Dispatchers.IO) {
        val personalizedFile = File(personalizedDir, "${documentId}_personalized.pdf")
        val sourceFile = if (personalizedFile.exists()) personalizedFile else File(originalsDir, "$documentId.pdf")
        if (!sourceFile.exists()) {
            throw IllegalArgumentException("PDF file not found for document $documentId")
        }

        val finalFileName = exportFileName?.let {
            if (it.endsWith(".pdf", ignoreCase = true)) it else "$it.pdf"
        } ?: "DocMorph_${documentId.take(8)}_personalized.pdf"

        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
            val contentValues = android.content.ContentValues().apply {
                put(android.provider.MediaStore.MediaColumns.DISPLAY_NAME, finalFileName)
                put(android.provider.MediaStore.MediaColumns.MIME_TYPE, "application/pdf")
                put(android.provider.MediaStore.MediaColumns.RELATIVE_PATH, android.os.Environment.DIRECTORY_DOWNLOADS + "/DocMorph")
            }

            val resolver = context.contentResolver
            val uri = resolver.insert(android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)
                ?: throw IllegalStateException("Failed to create MediaStore entry in Downloads")

            resolver.openOutputStream(uri)?.use { outputStream ->
                sourceFile.inputStream().use { inputStream ->
                    inputStream.copyTo(outputStream)
                }
            } ?: throw IllegalStateException("Failed to open output stream to Downloads")

            "Downloads/DocMorph/$finalFileName"
        } else {
            @Suppress("DEPRECATION")
            val downloadsDir = File(android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS), "DocMorph")
            if (!downloadsDir.exists()) downloadsDir.mkdirs()
            val destFile = File(downloadsDir, finalFileName)
            sourceFile.copyTo(destFile, overwrite = true)
            destFile.absolutePath
        }
    }

    fun getFileUri(file: File): Uri {
        val authority = "${context.packageName}.fileprovider"
        return androidx.core.content.FileProvider.getUriForFile(context, authority, file)
    }

    fun getFile(documentId: String, usePersonalized: Boolean = false): File {
        return if (usePersonalized) {
            val pFile = File(personalizedDir, "${documentId}_personalized.pdf")
            if (pFile.exists()) pFile else File(originalsDir, "$documentId.pdf")
        } else {
            File(originalsDir, "$documentId.pdf")
        }
    }

    fun createOpenIntent(documentId: String, usePersonalized: Boolean = true): android.content.Intent {
        val file = if (usePersonalized) {
            val pFile = File(personalizedDir, "${documentId}_personalized.pdf")
            if (pFile.exists()) pFile else File(originalsDir, "$documentId.pdf")
        } else {
            File(originalsDir, "$documentId.pdf")
        }

        if (!file.exists()) {
            throw IllegalArgumentException("PDF file not found for document $documentId")
        }

        val uri = getFileUri(file)
        return android.content.Intent(android.content.Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/pdf")
            addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
        }
    }

    fun createShareIntent(documentId: String, usePersonalized: Boolean = true): android.content.Intent {
        val file = if (usePersonalized) {
            val pFile = File(personalizedDir, "${documentId}_personalized.pdf")
            if (pFile.exists()) pFile else File(originalsDir, "$documentId.pdf")
        } else {
            File(originalsDir, "$documentId.pdf")
        }

        if (!file.exists()) {
            throw IllegalArgumentException("PDF file not found for document $documentId")
        }

        val uri = getFileUri(file)
        val shareIntent = android.content.Intent(android.content.Intent.ACTION_SEND).apply {
            type = "application/pdf"
            putExtra(android.content.Intent.EXTRA_STREAM, uri)
            putExtra(android.content.Intent.EXTRA_SUBJECT, file.name)
            addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }

        return android.content.Intent.createChooser(shareIntent, "Share Personalized Document").apply {
            addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
        }
    }

    private fun queryFileName(uri: Uri): String? {
        if (uri.scheme == "content") {
            context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (nameIndex != -1 && cursor.moveToFirst()) {
                    return cursor.getString(nameIndex)
                }
            }
        }
        return uri.path?.let { File(it).name }
    }
}

