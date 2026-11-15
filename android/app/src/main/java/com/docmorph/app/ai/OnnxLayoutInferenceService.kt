package com.docmorph.app.ai

import android.content.Context
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.InputStream
import java.nio.FloatBuffer
import kotlin.math.max
import kotlin.math.min

data class LayoutEntity(
    val entityType: String, // "student_name", "enrollment_number", "roll_number", "student_id", "page_number", "footer_region"
    val value: String,
    val normalizedBbox: List<Int>, // [x0, y0, x1, y1] normalized to [0, 1000]
    val confidence: Float,
    val tokenIndices: List<Int>
)

class OnnxLayoutInferenceService(private val context: Context) {

    private var ortEnv: OrtEnvironment? = null
    private var ortSession: OrtSession? = null

    init {
        initSession()
    }

    @Synchronized
    private fun initSession() {
        try {
            ortEnv = OrtEnvironment.getEnvironment()
            val modelBytes = context.assets.open("models/layout_classifier.onnx").use { it.readBytes() }
            ortSession = ortEnv?.createSession(modelBytes, OrtSession.SessionOptions())
        } catch (e: Exception) {
            android.util.Log.w("OnnxLayoutInference", "Failed to load ONNX model, falling back to heuristics: ${e.message}")
            ortSession = null
        }
    }

    fun isModelAvailable(): Boolean = ortSession != null

    fun predictPage(
        tokens: List<String>,
        bboxes: List<List<Int>>,
        pageHeight: Float = 1000f
    ): List<LayoutEntity> {
        if (tokens.isEmpty()) return emptyList()

        val nTokens = tokens.size
        val features = LayoutFeatureExtractor.extractFeatures(tokens, bboxes)

        val predictedLabels = mutableListOf<String>()
        val confidences = mutableListOf<Float>()

        val session = ortSession
        val env = ortEnv

        if (session != null && env != null) {
            try {
                // Flatten features into FloatBuffer [nTokens, 36]
                val floatBuffer = FloatBuffer.allocate(nTokens * 36)
                for (row in features) {
                    floatBuffer.put(row)
                }
                floatBuffer.rewind()

                val tensor = OnnxTensor.createTensor(env, floatBuffer, longArrayOf(nTokens.toLong(), 36L))
                val inputName = session.inputNames.iterator().next()
                val result = session.run(mapOf(inputName to tensor))

                // Output 0: labels (int64)
                val labelTensor = result.get(0).value as LongArray
                // Output 1: probabilities (float[nTokens, 10])
                @Suppress("UNCHECKED_CAST")
                val probaArray = result.get(1).value as Array<FloatArray>

                for (i in 0 until nTokens) {
                    val labelId = labelTensor[i].toInt()
                    val labelStr = ID2LABEL[labelId] ?: "O"
                    predictedLabels.add(labelStr)

                    var maxProb = 0.85f
                    if (i < probaArray.size) {
                        for (p in probaArray[i]) {
                            if (p > maxProb) maxProb = p
                        }
                    }
                    confidences.add(maxProb)
                }
                tensor.close()
                result.close()
            } catch (e: Exception) {
                android.util.Log.e("OnnxLayoutInference", "ONNX inference error, running heuristic fallback: ${e.message}")
                val fallback = heuristicLayoutPrediction(tokens, bboxes, pageHeight)
                predictedLabels.clear()
                predictedLabels.addAll(fallback.first)
                confidences.clear()
                confidences.addAll(fallback.second)
            }
        } else {
            val fallback = heuristicLayoutPrediction(tokens, bboxes, pageHeight)
            predictedLabels.addAll(fallback.first)
            confidences.addAll(fallback.second)
        }

        return assembleBioEntities(tokens, bboxes, predictedLabels, confidences)
    }

    private fun assembleBioEntities(
        tokens: List<String>,
        bboxes: List<List<Int>>,
        labels: List<String>,
        confidences: List<Float>
    ): List<LayoutEntity> {
        val entities = mutableListOf<LayoutEntity>()
        var currEntityType: String? = null
        val currTokenIndices = mutableListOf<Int>()
        val currConfidences = mutableListOf<Float>()

        fun flushCurrent() {
            if (currEntityType == null || currTokenIndices.isEmpty()) return

            val subTokens = currTokenIndices.map { tokens[it] }
            val rawVal = subTokens.joinToString(" ").trim()

            var cleanVal = rawVal
            if (currEntityType in listOf("enrollment_number", "roll_number", "student_id", "page_number")) {
                cleanVal = rawVal.replace(Regex("[()\\[\\]\\-|,;:]"), "").trim()
            }

            if (cleanVal.isNotEmpty()) {
                var minX = Int.MAX_VALUE
                var minY = Int.MAX_VALUE
                var maxX = Int.MIN_VALUE
                var maxY = Int.MIN_VALUE

                for (idx in currTokenIndices) {
                    val b = bboxes[idx]
                    minX = min(minX, b[0])
                    minY = min(minY, b[1])
                    maxX = max(maxX, b[2])
                    maxY = max(maxY, b[3])
                }

                val avgConf = if (currConfidences.isNotEmpty()) currConfidences.average().toFloat() else 0.85f

                entities.add(
                    LayoutEntity(
                        entityType = currEntityType!!,
                        value = cleanVal,
                        normalizedBbox = listOf(minX, minY, maxX, maxY),
                        confidence = (avgConf * 1000).toInt() / 1000.0f,
                        tokenIndices = currTokenIndices.toList()
                    )
                )
            }

            currEntityType = null
            currTokenIndices.clear()
            currConfidences.clear()
        }

        for (idx in tokens.indices) {
            val label = labels[idx]
            val conf = confidences[idx]

            if (label == "O") {
                flushCurrent()
                continue
            }

            val tagPrefix = label.substring(0, min(2, label.length))
            val entityTag = if (label.length > 2) label.substring(2).lowercase() else "footer"

            if (tagPrefix == "B-") {
                flushCurrent()
                currEntityType = entityTag
                currTokenIndices.add(idx)
                currConfidences.add(conf)
            } else if (tagPrefix == "I-") {
                if (currEntityType == entityTag) {
                    currTokenIndices.add(idx)
                    currConfidences.add(conf)
                } else {
                    flushCurrent()
                    currEntityType = entityTag
                    currTokenIndices.add(idx)
                    currConfidences.add(conf)
                }
            }
        }

        flushCurrent()
        return entities
    }

    /**
     * Exact Kotlin port of inference.py _heuristic_layout_prediction
     */
    fun heuristicLayoutPrediction(
        tokens: List<String>,
        bboxes: List<List<Int>>,
        pageHeight: Float
    ): Pair<List<String>, List<Float>> {
        val labels = mutableListOf<String>()
        val confidences = mutableListOf<Float>()

        val footerThresholdY = pageHeight * 0.75f

        for (i in tokens.indices) {
            val t = tokens[i]
            val b = bboxes[i]
            val y1 = b[3].toFloat()
            val isFooter = (y1 >= footerThresholdY)
            val clean = t.trim('(', ')', '[', ']', '-', '|', ',', '.', ':')

            if (isFooter) {
                if (clean.all { it.isDigit() } && clean.length in 1..3 && b[0] >= 400) {
                    labels.add("B-PAGE_NUMBER")
                    confidences.add(0.92f)
                } else if (clean.all { it.isDigit() } && clean.length in 8..15) {
                    labels.add("B-ENROLLMENT_ID")
                    confidences.add(0.90f)
                } else if (clean.all { it.isLetter() } && clean.length >= 2 && isTitle(clean)) {
                    labels.add("B-STUDENT_NAME")
                    confidences.add(0.85f)
                } else {
                    labels.add("B-FOOTER")
                    confidences.add(0.80f)
                }
            } else {
                labels.add("O")
                confidences.add(0.95f)
            }
        }

        return Pair(labels, confidences)
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

    fun close() {
        try {
            ortSession?.close()
            ortEnv?.close()
        } catch (e: Exception) {
            // ignore
        }
    }

    companion object {
        val ID2LABEL = mapOf(
            0 to "O",
            1 to "B-FOOTER",
            2 to "I-FOOTER",
            3 to "B-STUDENT_NAME",
            4 to "I-STUDENT_NAME",
            5 to "B-ENROLLMENT_ID",
            6 to "I-ENROLLMENT_ID",
            7 to "B-ROLL_NUMBER",
            8 to "I-ROLL_NUMBER",
            9 to "B-STUDENT_ID",
            10 to "I-STUDENT_ID",
            11 to "B-PAGE_NUMBER",
            12 to "I-PAGE_NUMBER"
        )
    }
}

