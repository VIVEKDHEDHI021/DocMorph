package com.docmorph.app.plugin

import android.net.Uri
import com.docmorph.app.ai.OnnxLayoutInferenceService
import com.docmorph.app.detection.DetectionCandidate
import com.docmorph.app.detection.DetectionOrchestrator
import com.docmorph.app.detection.FooterStatus
import com.docmorph.app.detection.ManualSelectionInput
import com.docmorph.app.detection.ProfileMatcher
import com.docmorph.app.detection.SelectionType
import com.docmorph.app.detection.SmartManualDetector
import com.docmorph.app.pdf.ExtractionResult
import com.docmorph.app.pdf.PdfExtractorService
import com.docmorph.app.pdf.PdfPersonalizerService
import com.docmorph.app.pdf.PersonalizationCandidate
import com.docmorph.app.security.SecureProfileManager
import com.docmorph.app.storage.LocalPdfStorage
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.io.File

@CapacitorPlugin(name = "DocMorphNative")
class DocMorphPlugin : Plugin() {

    private lateinit var profileManager: SecureProfileManager
    private lateinit var storage: LocalPdfStorage
    private lateinit var extractor: PdfExtractorService
    private lateinit var onnxService: OnnxLayoutInferenceService
    private lateinit var orchestrator: DetectionOrchestrator
    private lateinit var profileMatcher: ProfileMatcher
    private lateinit var personalizer: PdfPersonalizerService
    private lateinit var smartManualDetector: SmartManualDetector
    private val scope = CoroutineScope(Dispatchers.IO)

    // Cached candidates for fast profile re-matching
    private val candidateCache = mutableMapOf<String, List<DetectionCandidate>>()
    // Cached extraction results for manual selection analysis
    private val extractionCache = mutableMapOf<String, ExtractionResult>()

    override fun load() {
        super.load()
        val ctx = context
        profileManager = SecureProfileManager(ctx)
        storage = LocalPdfStorage(ctx)
        extractor = PdfExtractorService(ctx)
        onnxService = OnnxLayoutInferenceService(ctx)
        orchestrator = DetectionOrchestrator(onnxService)
        profileMatcher = ProfileMatcher()
        personalizer = PdfPersonalizerService(ctx)
        smartManualDetector = SmartManualDetector()
    }

    override fun handleOnDestroy() {
        onnxService.close()
        super.handleOnDestroy()
    }

    // --- Profile Management ---

    @PluginMethod
    fun saveProfile(call: PluginCall) {
        val fullName = call.getString("fullName")
        val enrollmentNumber = call.getString("enrollmentNumber")
        val rollNumber = call.getString("rollNumber")
        val studentId = call.getString("studentId")

        if (fullName.isNullOrBlank() || enrollmentNumber.isNullOrBlank()) {
            call.reject("fullName and enrollmentNumber are required")
            return
        }

        try {
            profileManager.saveProfile(fullName, enrollmentNumber, rollNumber, studentId)
            val ret = JSObject()
            ret.put("success", true)
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to save profile: ${e.message}", e)
        }
    }

    @PluginMethod
    fun getProfile(call: PluginCall) {
        try {
            val profile = profileManager.getProfile()
            val ret = JSObject()
            if (profile != null) {
                ret.put("hasProfile", true)
                val data = JSObject()
                data.put("fullName", profile["fullName"])
                data.put("enrollmentNumber", profile["enrollmentNumber"])
                data.put("rollNumber", profile["rollNumber"])
                data.put("studentId", profile["studentId"])
                data.put("updatedAt", profile["updatedAt"])
                ret.put("profile", data)
            } else {
                ret.put("hasProfile", false)
                ret.put("profile", null)
            }
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to get profile: ${e.message}", e)
        }
    }

    @PluginMethod
    fun deleteProfile(call: PluginCall) {
        try {
            profileManager.deleteProfile()
            val ret = JSObject()
            ret.put("success", true)
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to delete profile: ${e.message}", e)
        }
    }

    // --- Document Storage & Import ---

    @PluginMethod
    fun importPdfFromUri(call: PluginCall) {
        val uriString = call.getString("uri")
        if (uriString.isNullOrBlank()) {
            call.reject("uri is required")
            return
        }

        scope.launch {
            try {
                val uri = Uri.parse(uriString)
                val result = storage.importPdfFromUri(uri)
                if (result.success) {
                    val ret = JSObject()
                    ret.put("success", true)
                    ret.put("documentId", result.documentId)
                    ret.put("fileName", result.fileName)
                    ret.put("filePath", result.filePath)
                    ret.put("pageCount", result.pageCount)
                    ret.put("fileSizeBytes", result.fileSizeBytes)
                    call.resolve(ret)
                } else {
                    call.reject(result.errorMessage ?: "Failed to import PDF")
                }
            } catch (e: Exception) {
                call.reject("Failed to import PDF: ${e.message}", e)
            }
        }
    }

    @PluginMethod
    fun importPdfFromBase64(call: PluginCall) {
        val base64Data = call.getString("base64Data")
        val fileName = call.getString("fileName") ?: "document.pdf"

        if (base64Data.isNullOrBlank()) {
            call.reject("base64Data is required")
            return
        }

        scope.launch {
            try {
                val rawBase64 = if (base64Data.contains(",")) {
                    base64Data.substringAfter(",")
                } else {
                    base64Data
                }
                val bytes = android.util.Base64.decode(rawBase64, android.util.Base64.DEFAULT)
                val result = storage.importPdfFromBytes(fileName, bytes)
                if (result.success) {
                    val ret = JSObject()
                    ret.put("success", true)
                    ret.put("documentId", result.documentId)
                    ret.put("fileName", result.fileName)
                    ret.put("filePath", result.filePath)
                    ret.put("pageCount", result.pageCount)
                    ret.put("fileSizeBytes", result.fileSizeBytes)
                    call.resolve(ret)
                } else {
                    call.reject(result.errorMessage ?: "Failed to import PDF")
                }
            } catch (e: Exception) {
                call.reject("Failed to import PDF from base64: ${e.message}", e)
            }
        }
    }

    @PluginMethod
    fun extractPdfData(call: PluginCall) {
        val documentId = call.getString("documentId")
        val filePath = call.getString("filePath")

        if (documentId.isNullOrBlank() || filePath.isNullOrBlank()) {
            call.reject("documentId and filePath are required")
            return
        }

        scope.launch {
            try {
                val result = extractor.extractDocument(documentId, filePath)
                val ret = JSObject()
                ret.put("documentId", result.documentId)
                ret.put("totalPages", result.totalPages)
                ret.put("isScanned", result.isScanned)

                val pagesArray = JSArray()
                for (page in result.pages) {
                    val pageObj = JSObject()
                    pageObj.put("pageNumber", page.pageNumber)
                    pageObj.put("width", page.width)
                    pageObj.put("height", page.height)
                    pageObj.put("isScanned", page.isScanned)

                    val blocksArray = JSArray()
                    for (block in page.blocks) {
                        val blockObj = JSObject()
                        blockObj.put("text", block.text)

                        val bboxArray = JSArray()
                        block.bbox.forEach { bboxArray.put(it) }
                        blockObj.put("bbox", bboxArray)

                        val rawBboxArray = JSArray()
                        block.rawBbox.forEach { rawBboxArray.put(it) }
                        blockObj.put("rawBbox", rawBboxArray)

                        blockObj.put("fontName", block.fontName)
                        blockObj.put("fontSize", block.fontSize)
                        blocksArray.put(blockObj)
                    }
                    pageObj.put("blocks", blocksArray)
                    pagesArray.put(pageObj)
                }
                ret.put("pages", pagesArray)
                call.resolve(ret)
            } catch (oom: OutOfMemoryError) {
                System.gc()
                call.reject("Device ran out of memory while extracting PDF text. Please close background apps and try again.")
            } catch (e: Exception) {
                call.reject("Failed to extract PDF data: ${e.message}", e)
            }
        }
    }

    // --- Phase C: Universal AI & Footer Detection ---

    @PluginMethod
    fun analyzeDocument(call: PluginCall) {
        val documentId = call.getString("documentId")
        val filePath = call.getString("filePath")

        if (documentId.isNullOrBlank() || filePath.isNullOrBlank()) {
            call.reject("documentId and filePath are required")
            return
        }

        val pdfFile = File(filePath)
        if (!pdfFile.exists()) {
            call.reject("File not found at $filePath")
            return
        }

        scope.launch {
            try {
                // 1. Extract layout data (PDFBox with OCR fallback)
                val extractionResult = extractor.extractDocument(documentId, filePath)
                extractionCache[documentId] = extractionResult
                val savedProfile = profileManager.getProfile()

                // 2. Run multi-modal detection orchestrator with Phase B footer verification
                val orchestration = orchestrator.analyzeDocumentWithVerification(pdfFile, extractionResult, savedProfile)
                val candidates = orchestration.candidates
                candidateCache[documentId] = candidates

                val ret = JSObject()
                ret.put("documentId", documentId)
                ret.put("totalPages", extractionResult.totalPages)
                ret.put("isScanned", extractionResult.isScanned)
                ret.put("candidates", serializeCandidates(candidates))

                val fvObj = JSObject()
                fvObj.put("status", orchestration.footerVerification.status.name)
                fvObj.put("confidence", orchestration.footerVerification.confidence)
                fvObj.put("confirmedPagesCount", orchestration.footerVerification.confirmedPagesCount)
                fvObj.put("uncertainPagesCount", orchestration.footerVerification.uncertainPagesCount)
                fvObj.put("notFoundPagesCount", orchestration.footerVerification.notFoundPagesCount)
                fvObj.put("summaryMessage", orchestration.footerVerification.summaryMessage)
                ret.put("footerVerification", fvObj)

                call.resolve(ret)
            } catch (oom: OutOfMemoryError) {
                System.gc()
                call.reject("Device ran out of memory while analyzing document layout. Please close background apps and try again.")
            } catch (e: Exception) {
                call.reject("Failed to analyze document: ${e.message}", e)
            }
        }
    }

    @PluginMethod
    fun matchProfile(call: PluginCall) {
        val documentId = call.getString("documentId")
        if (documentId.isNullOrBlank()) {
            call.reject("documentId is required")
            return
        }

        val cached = candidateCache[documentId]
        if (cached == null) {
            call.reject("Document has not been analyzed yet. Run analyzeDocument first.")
            return
        }

        try {
            val savedProfile = profileManager.getProfile()
            val matched = profileMatcher.matchCandidates(cached, savedProfile)
            candidateCache[documentId] = matched

            val ret = JSObject()
            ret.put("documentId", documentId)
            ret.put("candidates", serializeCandidates(matched))
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to match profile: ${e.message}", e)
        }
    }

    @PluginMethod
    fun manualDetect(call: PluginCall) {
        val documentId = call.getString("documentId")
        val filePath = call.getString("filePath")
        val pageIndex = call.getInt("pageIndex") ?: 0
        val selectionTypeStr = call.getString("selectionType") ?: "area"
        val pageWidth = call.getDouble("pageWidth")?.toFloat() ?: 612f
        val pageHeight = call.getDouble("pageHeight")?.toFloat() ?: 792f
        val selectedText = call.getString("selectedText")

        if (documentId.isNullOrBlank()) {
            call.reject("documentId is required")
            return
        }

        scope.launch {
            try {
                var extraction = extractionCache[documentId]
                if (extraction == null && !filePath.isNullOrBlank()) {
                    val file = File(filePath)
                    if (file.exists()) {
                        extraction = extractor.extractDocument(documentId, filePath)
                        extractionCache[documentId] = extraction
                    }
                }

                if (extraction == null) {
                    call.reject("Document has not been analyzed yet and no valid filePath provided")
                    return@launch
                }

                if (pageIndex < 0 || pageIndex >= extraction.pages.size) {
                    call.reject("pageIndex $pageIndex out of range (0..${extraction.pages.size - 1})")
                    return@launch
                }

                val pageData = extraction.pages[pageIndex]

                val rawArray = call.getArray("rawBbox")
                val rawBbox = if (rawArray != null && rawArray.length() == 4) {
                    listOf(
                        rawArray.getDouble(0).toFloat(),
                        rawArray.getDouble(1).toFloat(),
                        rawArray.getDouble(2).toFloat(),
                        rawArray.getDouble(3).toFloat()
                    )
                } else null

                val normArray = call.getArray("normalizedBox")
                val normBbox = if (normArray != null && normArray.length() == 4) {
                    listOf(
                        normArray.getInt(0),
                        normArray.getInt(1),
                        normArray.getInt(2),
                        normArray.getInt(3)
                    )
                } else null

                val selType = if (selectionTypeStr.lowercase() == "text") SelectionType.TEXT else SelectionType.AREA

                val input = ManualSelectionInput(
                    documentId = documentId,
                    pageIndex = pageIndex,
                    selectionType = selType,
                    rawBbox = rawBbox,
                    normalizedBox = normBbox,
                    selectedText = selectedText,
                    pageWidth = pageWidth,
                    pageHeight = pageHeight
                )

                val savedProfile = profileManager.getProfile()
                val result = smartManualDetector.processSelection(input, pageData, savedProfile)

                // Phase E: If manual selection confirmed fields, merge them into candidateCache for personalization!
                if (result.footerStatus == FooterStatus.FOOTER_CONFIRMED && result.candidates.isNotEmpty()) {
                    val existing = candidateCache[documentId]?.toMutableList() ?: mutableListOf()
                    existing.removeAll { old ->
                        result.candidates.any { new -> new.pageIndex == old.pageIndex && new.fieldType == old.fieldType }
                    }
                    existing.addAll(result.candidates)
                    candidateCache[documentId] = existing
                }

                val ret = JSObject()
                ret.put("documentId", result.documentId)
                ret.put("pageIndex", result.pageIndex)
                ret.put("selectionType", result.selectionType.name.lowercase())

                val boxArr = JSArray()
                result.resolvedPdfBox.forEach { boxArr.put(it) }
                ret.put("resolvedPdfBox", boxArr)

                ret.put("extractedText", result.extractedText)
                ret.put("footerStatus", result.footerStatus.name)
                ret.put("confidence", result.confidence)
                ret.put("candidates", serializeCandidates(result.candidates))

                val negArr = JSArray()
                result.negativeReasons.forEach { negArr.put(it) }
                ret.put("negativeReasons", negArr)

                ret.put("summaryMessage", result.summaryMessage)

                call.resolve(ret)
            } catch (e: Exception) {
                call.reject("Manual detection failed: ${e.message}", e)
            }
        }
    }

    private fun serializeCandidates(candidates: List<DetectionCandidate>): JSArray {
        val array = JSArray()
        for (c in candidates) {
            val obj = JSObject()
            obj.put("id", c.id)
            obj.put("fieldType", c.fieldType)
            obj.put("detectedText", c.detectedText)
            obj.put("replacementText", c.replacementText)
            obj.put("confidence", c.confidence)
            obj.put("pageIndex", c.pageIndex)

            val normBox = JSArray()
            c.normalizedBox.forEach { normBox.put(it) }
            obj.put("normalizedBox", normBox)

            val pdfBox = JSArray()
            c.pdfPointBox.forEach { pdfBox.put(it) }
            obj.put("pdfPointBox", pdfBox)

            obj.put("fontName", c.fontName)
            obj.put("fontSize", c.fontSize)
            obj.put("pairId", c.pairId)
            obj.put("requiresConfirmation", c.requiresConfirmation)
            obj.put("isOcr", c.isOcr)

            array.put(obj)
        }
        return array
    }

    @PluginMethod
    fun getPreviewUrl(call: PluginCall) {
        val filePath = call.getString("filePath")
        if (filePath.isNullOrBlank()) {
            call.reject("filePath is required")
            return
        }

        val file = File(filePath)
        if (!file.exists()) {
            call.reject("File does not exist at $filePath")
            return
        }

        val webUrl = bridge.scheme + "://" + bridge.host + "/_capacitor_file_" + file.absolutePath
        val ret = JSObject()
        ret.put("url", webUrl)
        ret.put("filePath", file.absolutePath)
        call.resolve(ret)
    }

    @PluginMethod
    fun getPdfBase64(call: PluginCall) {
        val documentId = call.getString("documentId")
        val which = call.getString("which") ?: "original"
        val filePath = call.getString("filePath")

        val targetFile: File = when {
            !filePath.isNullOrBlank() -> File(filePath)
            !documentId.isNullOrBlank() -> storage.getFile(documentId, which == "personalized")
            else -> {
                call.reject("documentId or filePath is required")
                return
            }
        }

        if (!targetFile.exists()) {
            call.reject("PDF file does not exist at ${targetFile.absolutePath}")
            return
        }

        scope.launch {
            try {
                val bytes = targetFile.readBytes()
                val base64 = android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP)
                val ret = JSObject()
                ret.put("base64", base64)
                ret.put("size", bytes.size)
                call.resolve(ret)
            } catch (e: Exception) {
                call.reject("Failed to read PDF file: ${e.message}", e)
            }
        }
    }

    @PluginMethod
    fun listDocuments(call: PluginCall) {
        scope.launch {
            try {
                val docs = storage.getAllDocuments()
                val list = JSArray()
                for (doc in docs) {
                    val obj = JSObject()
                    obj.put("documentId", doc.documentId)
                    obj.put("fileName", doc.fileName)
                    obj.put("originalPath", doc.originalPath)
                    obj.put("personalizedPath", doc.personalizedPath)
                    obj.put("pageCount", doc.pageCount)
                    obj.put("isScanned", doc.isScanned)
                    obj.put("fileSizeBytes", doc.fileSizeBytes)
                    obj.put("status", doc.status)
                    obj.put("createdAt", doc.createdAt)
                    obj.put("updatedAt", doc.updatedAt)
                    list.put(obj)
                }
                val ret = JSObject()
                ret.put("documents", list)
                call.resolve(ret)
            } catch (e: Exception) {
                call.reject("Failed to list documents: ${e.message}", e)
            }
        }
    }

    @PluginMethod
    fun deleteDocument(call: PluginCall) {
        val documentId = call.getString("documentId")
        if (documentId.isNullOrBlank()) {
            call.reject("documentId is required")
            return
        }

        candidateCache.remove(documentId)
        scope.launch {
            try {
                val success = storage.deleteDocument(documentId)
                val ret = JSObject()
                ret.put("success", success)
                call.resolve(ret)
            } catch (e: Exception) {
                call.reject("Failed to delete document: ${e.message}", e)
            }
        }
    }

    // --- Personalization Engine ---

    @PluginMethod
    fun personalizeDocument(call: PluginCall) {
        val documentId = call.getString("documentId")
        if (documentId.isNullOrBlank()) {
            call.reject("documentId is required")
            return
        }

        scope.launch {
            try {
                val profile = profileManager.getProfile()
                val profileName = profile?.get("fullName") ?: ""
                val profileEnrollment = profile?.get("enrollmentNumber") ?: ""

                val candidateList = mutableListOf<PersonalizationCandidate>()
                val passedArray = call.getArray("confirmedCandidates")

                if (passedArray != null && passedArray.length() > 0) {
                    for (i in 0 until passedArray.length()) {
                        val obj = passedArray.getJSONObject(i)
                        val fieldType = obj.optString("fieldType", "student_name")
                        val originalValue = obj.optString("originalValue", "")

                        var repValue = obj.optString("replacementText", "")
                        if (repValue.isBlank()) {
                            repValue = if (fieldType == "student_name") profileName else profileEnrollment
                        }

                        val bboxArr = obj.optJSONArray("pdfPointBox") ?: obj.optJSONArray("rawBbox")
                        val rawBbox = if (bboxArr != null && bboxArr.length() >= 4) {
                            listOf(
                                bboxArr.getDouble(0).toFloat(),
                                bboxArr.getDouble(1).toFloat(),
                                bboxArr.getDouble(2).toFloat(),
                                bboxArr.getDouble(3).toFloat()
                            )
                        } else {
                            listOf(50f, 750f, 250f, 770f)
                        }

                        candidateList.add(
                            PersonalizationCandidate(
                                pageIndex = obj.optInt("pageIndex", 0),
                                fieldType = fieldType,
                                originalValue = originalValue,
                                replacementValue = repValue,
                                rawBbox = rawBbox,
                                pairId = if (obj.has("pairId") && !obj.isNull("pairId")) obj.getString("pairId") else null,
                                isInverted = obj.optBoolean("isInverted", false),
                                isOcr = obj.optBoolean("isOcr", false),
                                fontName = if (obj.has("fontName") && !obj.isNull("fontName")) obj.getString("fontName") else null,
                                fontSize = obj.optDouble("fontSize", 10.0).toFloat()
                            )
                        )
                    }
                } else {
                    // Fall back to cached candidates from previous analyzeDocument
                    val cached = candidateCache[documentId] ?: emptyList()
                    for (cand in cached) {
                        val repValue = if (cand.fieldType == "student_name") profileName else profileEnrollment
                        candidateList.add(
                            PersonalizationCandidate(
                                pageIndex = cand.pageIndex,
                                fieldType = cand.fieldType,
                                originalValue = cand.detectedText,
                                replacementValue = repValue,
                                rawBbox = cand.pdfPointBox,
                                pairId = cand.pairId,
                                isInverted = false,
                                isOcr = false,
                                fontName = cand.fontName,
                                fontSize = cand.fontSize
                            )
                        )
                    }
                }

                if (candidateList.isEmpty()) {
                    call.reject("No candidates available to personalize for document $documentId")
                    return@launch
                }

                val result = personalizer.personalizeDocument(documentId, candidateList)
                val ret = JSObject()
                ret.put("success", true)
                ret.put("documentId", result.documentId)
                ret.put("personalizedPath", result.personalizedPath)
                ret.put("personalizedPreviewUrl", bridge.scheme + "://" + bridge.host + "/_capacitor_file_" + result.personalizedPath)
                ret.put("totalReplaced", result.totalReplaced)
                ret.put("originalSha256", result.originalSha256)
                ret.put("personalizedSha256", result.personalizedSha256)
                ret.put("verificationPassed", result.verificationReport.passed)

                val vrObj = JSObject()
                vrObj.put("passed", result.verificationReport.passed)
                vrObj.put("totalChecks", result.verificationReport.totalChecks)
                val pageArr = JSArray()
                for (pr in result.verificationReport.pageResults) {
                    val pObj = JSObject()
                    pObj.put("pageIndex", pr.pageIndex)
                    pObj.put("pageNumber", pr.pageNumber)
                    pObj.put("passed", pr.passed)
                    pObj.put("status", pr.status)
                    val pErr = JSArray()
                    pr.errors.forEach { pErr.put(it) }
                    pObj.put("errors", pErr)
                    val pWarn = JSArray()
                    pr.warnings.forEach { pWarn.put(it) }
                    pObj.put("warnings", pWarn)
                    pageArr.put(pObj)
                }
                vrObj.put("pageResults", pageArr)
                ret.put("verificationReport", vrObj)

                val warningsArray = JSArray()
                for (w in result.warnings) {
                    warningsArray.put(w)
                }
                ret.put("warnings", warningsArray)

                call.resolve(ret)
            } catch (oom: OutOfMemoryError) {
                System.gc()
                call.reject("Device ran out of memory during PDF personalization. Please close background apps and try again.")
            } catch (e: Exception) {
                call.reject("Personalization failed: ${e.message}", e)
            }
        }
    }

    // --- Export, Open & Share ---

    @PluginMethod
    fun exportPdfToDownloads(call: PluginCall) {
        val documentId = call.getString("documentId")
        if (documentId.isNullOrBlank()) {
            call.reject("documentId is required")
            return
        }
        val fileName = call.getString("fileName")

        scope.launch {
            try {
                val exportPath = storage.exportToPublicDownloads(documentId, fileName)
                val ret = JSObject()
                ret.put("success", true)
                ret.put("exportPath", exportPath)
                call.resolve(ret)
            } catch (e: Exception) {
                call.reject("Export to Downloads failed: ${e.message}", e)
            }
        }
    }

    @PluginMethod
    fun openPdf(call: PluginCall) {
        val documentId = call.getString("documentId")
        if (documentId.isNullOrBlank()) {
            call.reject("documentId is required")
            return
        }
        val which = call.getString("which") ?: "personalized"

        try {
            val intent = storage.createOpenIntent(documentId, which != "original")
            context.startActivity(intent)
            val ret = JSObject()
            ret.put("success", true)
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to open PDF: ${e.message}", e)
        }
    }

    @PluginMethod
    fun sharePdf(call: PluginCall) {
        val documentId = call.getString("documentId")
        if (documentId.isNullOrBlank()) {
            call.reject("documentId is required")
            return
        }
        val which = call.getString("which") ?: "personalized"

        try {
            val intent = storage.createShareIntent(documentId, which != "original")
            context.startActivity(intent)
            val ret = JSObject()
            ret.put("success", true)
            call.resolve(ret)
        } catch (e: Exception) {
            call.reject("Failed to share PDF: ${e.message}", e)
        }
    }
}
