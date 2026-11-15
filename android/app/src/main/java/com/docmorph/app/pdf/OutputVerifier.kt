package com.docmorph.app.pdf

import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import java.io.File

data class VerificationTarget(
    val pageIndex: Int, // 0-based
    val originalValue: String,
    val replacementValue: String
)

data class OutputVerificationReport(
    val passed: Boolean,
    val totalChecks: Int,
    val errors: List<String>,
    val warnings: List<String>
)

class OutputVerificationException(message: String, val report: OutputVerificationReport) : Exception(message)

class OutputVerifier {

    /**
     * Independently audits the generated personalized PDF:
     * 1. Output file structural validity and page count preservation.
     * 2. Confirms that replacement values are successfully extractable.
     * 3. Confirms that original values are COMPLETELY PURGED (proving content-stream deletion).
     */
    fun verifyOutput(
        outputFile: File,
        expectedPageCount: Int,
        targets: List<VerificationTarget>
    ): OutputVerificationReport {
        val errors = mutableListOf<String>()
        val warnings = mutableListOf<String>()
        var totalChecks = 0

        // Check 1: File existence and size
        totalChecks++
        if (!outputFile.exists() || outputFile.length() == 0L) {
            errors.add("Output file does not exist or is empty (0 bytes)")
            val report = OutputVerificationReport(
                passed = false,
                totalChecks = totalChecks,
                errors = errors,
                warnings = warnings
            )
            throw OutputVerificationException("Verification failed: Output file missing or empty", report)
        }

        // Check 2: Load document and verify page count
        totalChecks++
        val doc: PDDocument
        try {
            doc = PDDocument.load(outputFile)
        } catch (e: Exception) {
            errors.add("Failed to parse generated output PDF: ${e.message}")
            val report = OutputVerificationReport(
                passed = false,
                totalChecks = totalChecks,
                errors = errors,
                warnings = warnings
            )
            throw OutputVerificationException("Verification failed: Output PDF invalid", report)
        }

        doc.use {
            if (doc.numberOfPages != expectedPageCount) {
                errors.add("Page count mismatch: expected $expectedPageCount, got ${doc.numberOfPages}")
            }

            // Check 3: Page-by-page text assertions
            val stripper = PDFTextStripper()
            val targetsByPage = targets.groupBy { it.pageIndex }

            for ((pageIdx, pageTargets) in targetsByPage) {
                if (pageIdx >= doc.numberOfPages) {
                    errors.add("Target page index $pageIdx out of bounds (total pages: ${doc.numberOfPages})")
                    continue
                }

                stripper.startPage = pageIdx + 1
                stripper.endPage = pageIdx + 1
                val extractedText = stripper.getText(doc) ?: ""

                for (target in pageTargets) {
                    totalChecks++

                    val origClean = target.originalValue.trim()
                    val repClean = target.replacementValue.trim()

                    // Assertion A: Replacement value MUST appear on the page
                    if (repClean.isNotEmpty()) {
                        val foundReplacement = extractedText.contains(repClean, ignoreCase = true)
                        if (!foundReplacement) {
                            val tokens = repClean.split(" ").filter { it.length > 2 }
                            val foundTokens = tokens.isNotEmpty() && tokens.all { extractedText.contains(it, ignoreCase = true) }
                            if (!foundTokens) {
                                errors.add("Page ${pageIdx + 1}: Replacement value '$repClean' was not found in output text.")
                            }
                        }
                    }

                    // Assertion B: Original purged value MUST be completely absent from the page
                    if (origClean.isNotEmpty()) {
                        val originalStillPresent = extractedText.contains(origClean, ignoreCase = true)
                        if (originalStillPresent) {
                            errors.add("Page ${pageIdx + 1}: Original value '$origClean' is still extractable! True redaction failed.")
                        }
                    }
                }
            }
        }

        val passed = errors.isEmpty()
        val report = OutputVerificationReport(
            passed = passed,
            totalChecks = totalChecks,
            errors = errors,
            warnings = warnings
        )

        if (!passed) {
            // Delete corrupt or failed output file
            if (outputFile.exists()) {
                outputFile.delete()
            }
            throw OutputVerificationException(
                "Output verification failed with ${errors.size} error(s): ${errors.first()}",
                report
            )
        }

        return report
    }
}

