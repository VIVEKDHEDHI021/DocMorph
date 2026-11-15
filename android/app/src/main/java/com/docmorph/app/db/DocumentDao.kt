package com.docmorph.app.db

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update

@Dao
interface DocumentDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertDocument(document: DocumentEntity)

    @Update
    suspend fun updateDocument(document: DocumentEntity)

    @Query("SELECT * FROM documents ORDER BY createdAt DESC")
    suspend fun getAllDocuments(): List<DocumentEntity>

    @Query("SELECT * FROM documents WHERE documentId = :id LIMIT 1")
    suspend fun getDocumentById(id: String): DocumentEntity?

    @Delete
    suspend fun deleteDocument(document: DocumentEntity)

    @Query("DELETE FROM documents WHERE documentId = :id")
    suspend fun deleteDocumentById(id: String)
}

