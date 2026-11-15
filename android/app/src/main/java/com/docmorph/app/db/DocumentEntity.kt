package com.docmorph.app.db

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "documents")
data class DocumentEntity(
    @PrimaryKey
    val documentId: String,
    val fileName: String,
    val originalPath: String,
    val personalizedPath: String? = null,
    val pageCount: Int,
    val isScanned: Boolean = false,
    val fileSizeBytes: Long,
    val status: String, // e.g. "IMPORTED", "EXTRACTED", "PERSONALIZED", "FAILED"
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
)

