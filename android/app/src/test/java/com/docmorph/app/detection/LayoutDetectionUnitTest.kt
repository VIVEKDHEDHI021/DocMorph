package com.docmorph.app.detection

import com.docmorph.app.ai.LayoutFeatureExtractor
import com.docmorph.app.pdf.NativeTextBlock
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

class LayoutDetectionUnitTest {

    @Test
    fun test36FeatureExtractorParityWithPython() {
        val tokens = listOf("Vivek", "Dhedhi", "(92400120571)", "Page", "1")
        val bboxes = listOf(
            listOf(100, 920, 180, 940),
            listOf(185, 920, 280, 940),
            listOf(285, 920, 420, 940),
            listOf(800, 920, 840, 940),
            listOf(845, 920, 860, 940)
        )

        val kotlinFeatures = LayoutFeatureExtractor.extractFeatures(tokens, bboxes)
        assertEquals(5, kotlinFeatures.size)
        assertEquals(36, kotlinFeatures[0].size)

        // Python reference features
        val pyRef = arrayOf(
            floatArrayOf(0.100000001f, 0.920000017f, 0.180000007f, 0.940000000f, 0.140000001f, 0.930000007f, 0.060000000f, 0.100000001f, 0.820000000f, 4.0f, 1.0f, 1.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.16666667f, 0.0f, 1.0f, 0.0f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.005f, 0.0f, 0.0f, 0.0f, 0.0f),
            floatArrayOf(0.185000002f, 0.920000017f, 0.280000001f, 0.940000000f, 0.232500002f, 0.930000007f, 0.060000000f, 0.185000002f, 0.720000000f, 4.75f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.200000003f, 0.0f, 1.0f, 0.0f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.005f, 0.0f, 0.005f, 0.0f, 0.0f, 0.0f, 0.0f),
            floatArrayOf(0.285000000f, 0.920000017f, 0.420000000f, 0.940000000f, 0.352500000f, 0.930000007f, 0.060000000f, 0.285000000f, 0.580000000f, 6.75f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.433333340f, 0.846153855f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.005f, 0.0f, 0.380f, 0.0f, 0.0f, 0.0f, 0.0f),
            floatArrayOf(0.800000012f, 0.920000017f, 0.840000000f, 0.940000000f, 0.820000000f, 0.930000007f, 0.060000000f, 0.800000012f, 0.160000000f, 2.0f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.133333340f, 0.0f, 1.0f, 0.0f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.380f, 0.0f, 0.005f, 0.0f, 0.0f, 0.0f, 1.0f),
            floatArrayOf(0.845000029f, 0.920000017f, 0.860000014f, 0.940000000f, 0.852500021f, 0.930000007f, 0.060000000f, 0.845000029f, 0.140000000f, 0.75f, 1.0f, 1.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.033333335f, 1.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 1.0f, 0.0f, 0.005f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f)
        )

        for (tokenIdx in 0 until 5) {
            for (dim in 0 until 36) {
                val expected = pyRef[tokenIdx][dim]
                val actual = kotlinFeatures[tokenIdx][dim]
                assertTrue(
                    "Feature mismatch at token $tokenIdx dim $dim (expected=$expected, actual=$actual)",
                    abs(expected - actual) < 0.01f
                )
            }
        }
    }

    @Test
    fun testUnlabelledIdentityPairDetection() {
        val detector = UnlabelledIdentityDetector()

        // 1. Bracket format: "Vivek Dhedhi (92400120571)"
        val bracketBlock = NativeTextBlock(
            text = "Vivek Dhedhi (92400120571)",
            bbox = listOf(100f, 920f, 400f, 940f),
            rawBbox = listOf(50f, 750f, 200f, 770f),
            fontName = "Helvetica",
            fontSize = 10f
        )
        val matches1 = detector.detectUnlabelledPairs(listOf(bracketBlock))
        assertEquals(1, matches1.size)
        assertEquals("Vivek Dhedhi", matches1[0].name)
        assertEquals("92400120571", matches1[0].identifier)
        assertEquals("enrollment_number", matches1[0].identifierType)
        assertFalse(matches1[0].isInverted)
        assertNotNull(matches1[0].pairId)

        // 2. Delimiter format: "Priya Sharma - 92400120588"
        val delimBlock = NativeTextBlock(
            text = "Priya Sharma - 92400120588",
            bbox = listOf(100f, 920f, 400f, 940f),
            rawBbox = listOf(50f, 750f, 200f, 770f)
        )
        val matches2 = detector.detectUnlabelledPairs(listOf(delimBlock))
        assertEquals(1, matches2.size)
        assertEquals("Priya Sharma", matches2[0].name)
        assertEquals("92400120588", matches2[0].identifier)

        // 3. Inverted format: "92400120599 - Rahul Verma"
        val invBlock = NativeTextBlock(
            text = "92400120599 - Rahul Verma",
            bbox = listOf(100f, 920f, 400f, 940f),
            rawBbox = listOf(50f, 750f, 200f, 770f)
        )
        val matches3 = detector.detectUnlabelledPairs(listOf(invBlock))
        assertEquals(1, matches3.size)
        assertEquals("Rahul Verma", matches3[0].name)
        assertEquals("92400120599", matches3[0].identifier)
        assertTrue(matches3[0].isInverted)

        // 4. Standalone page numbers must be excluded
        val pageBlock = NativeTextBlock(
            text = "Page 1 of 10",
            bbox = listOf(800f, 920f, 850f, 940f),
            rawBbox = listOf(500f, 750f, 550f, 770f)
        )
        val matches4 = detector.detectUnlabelledPairs(listOf(pageBlock))
        assertTrue(matches4.isEmpty())

        // 5. Academic stop words must not match as student names
        val deptBlock = NativeTextBlock(
            text = "Department of Computer Engineering (GTU)",
            bbox = listOf(100f, 920f, 400f, 940f),
            rawBbox = listOf(50f, 750f, 200f, 770f)
        )
        val matches5 = detector.detectUnlabelledPairs(listOf(deptBlock))
        assertTrue(matches5.isEmpty())
    }

    @Test
    fun testPageNumberExclusion() {
        val detector = UnlabelledIdentityDetector()
        assertNull(detector.classifyIdentifier("Page 1 of 12"))
        assertNull(detector.classifyIdentifier("1 / 5"))
        assertNull(detector.classifyIdentifier("12"))
        assertEquals("enrollment_number", detector.classifyIdentifier("92400120571"))
        assertEquals("roll_number", detector.classifyIdentifier("2501"))
    }
}

