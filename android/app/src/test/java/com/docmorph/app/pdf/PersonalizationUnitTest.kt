package com.docmorph.app.pdf

import android.content.res.AssetManager
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.contentstream.operator.Operator
import com.tom_roush.pdfbox.pdfparser.PDFStreamParser
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.pdmodel.PDPage
import com.tom_roush.pdfbox.pdmodel.PDPageContentStream
import com.tom_roush.pdfbox.pdmodel.common.PDRectangle
import com.tom_roush.pdfbox.pdmodel.font.PDType1Font
import com.tom_roush.pdfbox.text.PDFTextStripper
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.BeforeClass
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.mockito.ArgumentMatchers.anyString
import org.mockito.Mockito
import java.io.File
import java.io.FileInputStream
import java.io.InputStream
import java.security.MessageDigest

class PersonalizationUnitTest {

    companion object {
        @JvmStatic
        @BeforeClass
        fun setupPdfBoxResourceLoader() {
            try {
                val mockAssets = Mockito.mock(AssetManager::class.java)
                Mockito.`when`(mockAssets.open(anyString())).thenAnswer { invocation ->
                    val path = invocation.arguments[0] as String
                    val candidates = listOf(
                        File("src/main/assets", path),
                        File("android/app/src/main/assets", path),
                        File("../android/app/src/main/assets", path)
                    )
                    var stream: InputStream? = null
                    for (c in candidates) {
                        if (c.exists()) {
                            stream = c.inputStream()
                            break
                        }
                    }
                    stream ?: throw java.io.FileNotFoundException("Asset not found: $path")
                }

                val field = PDFBoxResourceLoader::class.java.getDeclaredField("ASSET_MANAGER")
                field.isAccessible = true
                field.set(null, mockAssets)
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    @get:Rule
    val tempFolder = TemporaryFolder()

    @Test
    fun testTrueContentStreamTextDeletionAndVectorPreservation() {
        val originalPdf = tempFolder.newFile("test_academic.pdf")
        val personalizedPdf = tempFolder.newFile("test_academic_personalized.pdf")

        // 1. Create a synthetic academic document with vector graphics and student footer
        createSyntheticAcademicPdf(originalPdf)

        val shaBefore = computeSha256(originalPdf)

        // Verify original PDF contains old student credentials
        PDDocument.load(originalPdf).use { doc ->
            val stripper = PDFTextStripper()
            val origText = stripper.getText(doc)
            assertTrue("Original must contain Vivek Dhedhi", origText.contains("Vivek Dhedhi"))
            assertTrue("Original must contain 92400120571", origText.contains("92400120571"))
        }

        // Count vector operators before redaction
        val vectorOpsBefore: Int
        PDDocument.load(originalPdf).use { doc ->
            val parser = PDFStreamParser(doc.getPage(0))
            parser.parse()
            vectorOpsBefore = parser.tokens.filterIsInstance<Operator>().count {
                it.name in listOf("m", "l", "re", "S", "s", "f", "F")
            }
        }
        assertTrue("Original must have vector operators (borders and divider)", vectorOpsBefore > 0)

        // 2. Perform Content-Stream Redaction & Replacement
        val redactor = ContentStreamRedactor()
        val formatter = TypographyFormatter()
        val verifier = OutputVerifier()

        PDDocument.load(originalPdf).use { doc ->
            for (pageIdx in 0 until doc.numberOfPages) {
                val page = doc.getPage(pageIdx)
                val pageH = (page.cropBox ?: page.mediaBox).height

                // Footer candidate coordinates (top-down points: line at bottom y ~ 740 to 760)
                val targets = listOf(
                    RedactionTarget(
                        originalText = "Vivek Dhedhi (92400120571)",
                        rawBbox = listOf(50f, 740f, 300f, 760f),
                        pageIndex = pageIdx
                    )
                )

                // Purge old content stream tokens
                val purged = redactor.redactPage(doc, page, targets)
                assertTrue("Must purge at least one text operator", purged > 0)

                // Draw new personalized replacement text at exact baseline
                val newText = "Aarav Mehta (92400199999)"
                val font = PDType1Font.HELVETICA
                val fitted = formatter.calculateFittedFontSize(newText, font, 10f, 300f)

                PDPageContentStream(doc, page, PDPageContentStream.AppendMode.APPEND, true, true).use { cs ->
                    cs.beginText()
                    cs.setFont(fitted.font, fitted.fontSize)
                    cs.newLineAtOffset(50f, pageH - 760f)
                    cs.showText(newText)
                    cs.endText()
                }
            }

            doc.save(personalizedPdf)
        }

        // 3. Assert Source Immutability
        val shaAfter = computeSha256(originalPdf)
        assertEquals("Original PDF hash must be strictly conserved", shaBefore, shaAfter)

        // 4. Assert True Text Deletion & Replacement via PDFTextStripper
        PDDocument.load(personalizedPdf).use { doc ->
            val stripper = PDFTextStripper()
            for (p in 1..doc.numberOfPages) {
                stripper.startPage = p
                stripper.endPage = p
                val pageText = stripper.getText(doc)

                // Old values MUST be 100% absent
                assertFalse("Old student name must be completely absent", pageText.contains("Vivek Dhedhi"))
                assertFalse("Old enrollment must be completely absent", pageText.contains("92400120571"))

                // New values MUST be present
                assertTrue("New student name must be extractable", pageText.contains("Aarav Mehta"))
                assertTrue("New enrollment must be extractable", pageText.contains("92400199999"))
            }

            // 5. Assert Vector Preservation: vector lines/rules must still exist
            val parser = PDFStreamParser(doc.getPage(0))
            parser.parse()
            val vectorOpsAfter = parser.tokens.filterIsInstance<Operator>().count {
                it.name in listOf("m", "l", "re", "S", "s", "f", "F")
            }
            assertEquals("Vector graphics count must be conserved", vectorOpsBefore, vectorOpsAfter)
        }

        // 6. Run OutputVerifier
        val verificationTargets = listOf(
            VerificationTarget(0, "Vivek Dhedhi (92400120571)", "Aarav Mehta (92400199999)"),
            VerificationTarget(1, "Vivek Dhedhi (92400120571)", "Aarav Mehta (92400199999)")
        )
        val report = verifier.verifyOutput(personalizedPdf, 2, verificationTargets)
        assertTrue("Output verification must pass", report.passed)
        assertEquals(0, report.errors.size)
    }

    @Test
    fun testAdaptiveFontScalingUnderNarrowConstraints() {
        val formatter = TypographyFormatter()
        val font = PDType1Font.HELVETICA

        // Normal text in ample width (no scaling needed)
        val normal = formatter.calculateFittedFontSize("Vivek Dhedhi", font, 11f, 250f)
        assertEquals(11f, normal.fontSize, 0.01f)
        assertFalse(normal.hasOverflow)

        // Very long student name in restricted width (must scale down gracefully, >= 6.0pt)
        val veryLongName = "Alexander Bartholomew Montgomery The Third"
        val scaled = formatter.calculateFittedFontSize(veryLongName, font, 12f, 100f)
        assertTrue("Font size must be scaled down", scaled.fontSize < 12f)
        assertTrue("Font size must not drop below minimum 6.0pt", scaled.fontSize >= 6.0f)
        assertNotNull(scaled.warningMessage)

        // Pathological overflow test
        val extreme = formatter.calculateFittedFontSize(
            "Extremely Long Student Name That Will Exceed Even Minimum Bounds Under Impossible 10pt Width",
            font, 12f, 10f
        )
        assertEquals(6.0f, extreme.fontSize, 0.01f)
        assertTrue(extreme.hasOverflow)
    }

    @Test
    fun testTypographyFontResolution() {
        val formatter = TypographyFormatter()

        assertTrue(formatter.resolveFont("Times-Roman").name.contains("Times", ignoreCase = true))
        assertTrue(formatter.resolveFont("TimesNewRoman,Bold").name.contains("Times", ignoreCase = true))
        assertTrue(formatter.resolveFont("Courier-Oblique").name.contains("Courier", ignoreCase = true))
        assertTrue(formatter.resolveFont("Arial").name.contains("Helvetica", ignoreCase = true))
        assertTrue(formatter.resolveFont("Calibri-Bold").name.contains("Helvetica", ignoreCase = true))
    }

    private fun createSyntheticAcademicPdf(file: File) {
        PDDocument().use { doc ->
            for (p in 0 until 2) {
                val page = PDPage(PDRectangle.A4)
                doc.addPage(page)

                PDPageContentStream(doc, page).use { cs ->
                    // 1. Draw vector border around page
                    cs.setLineWidth(1.5f)
                    cs.setStrokingColor(0.2f, 0.2f, 0.2f)
                    cs.addRect(30f, 30f, 535f, 782f)
                    cs.stroke()

                    // 2. Header text
                    cs.beginText()
                    cs.setFont(PDType1Font.HELVETICA_BOLD, 14f)
                    cs.newLineAtOffset(50f, 800f)
                    cs.showText("MARWADI UNIVERSITY - DEPARTMENT OF ICT")
                    cs.endText()

                    // 3. Body text
                    cs.beginText()
                    cs.setFont(PDType1Font.HELVETICA, 11f)
                    cs.newLineAtOffset(50f, 750f)
                    cs.showText("Practical Assignment 01: Relational Database Systems")
                    cs.newLineAtOffset(0f, -20f)
                    cs.showText("Page ${p + 1} of 2 - Lab Manual Documentation")
                    cs.endText()

                    // 4. Vector horizontal footer divider line
                    cs.setLineWidth(0.8f)
                    cs.setStrokingColor(0.5f, 0.5f, 0.5f)
                    cs.moveTo(50f, 100f)
                    cs.lineTo(545f, 100f)
                    cs.stroke()

                    // 5. Student identity in footer (PDF user-space: y = 82pt corresponds to ~760 top-down)
                    cs.beginText()
                    cs.setFont(PDType1Font.HELVETICA, 10f)
                    cs.newLineAtOffset(50f, 82f)
                    cs.showText("Vivek Dhedhi (92400120571)")
                    cs.endText()

                    // Page number on right
                    cs.beginText()
                    cs.setFont(PDType1Font.HELVETICA, 10f)
                    cs.newLineAtOffset(480f, 82f)
                    cs.showText("Page ${p + 1}")
                    cs.endText()
                }
            }
            doc.save(file)
        }
    }

    private fun computeSha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { fis ->
            val buf = ByteArray(8192)
            var n: Int
            while (fis.read(buf).also { n = it } != -1) {
                digest.update(buf, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
