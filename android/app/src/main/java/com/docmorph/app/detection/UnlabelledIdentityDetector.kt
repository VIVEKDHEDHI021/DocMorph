package com.docmorph.app.detection

import com.docmorph.app.pdf.NativeTextBlock
import java.util.UUID

data class IdentityMatch(
    val name: String,
    val identifier: String,
    val identifierType: String, // "enrollment_number", "roll_number", "student_id"
    val pairId: String,
    val isInverted: bool = false,
    val nameBlock: NativeTextBlock,
    val idBlock: NativeTextBlock,
    val confidence: Float
)

typealias bool = Boolean

class UnlabelledIdentityDetector {

    companion object {
        val ACADEMIC_STOP_WORDS = setOf(
            "computer engineering", "information technology", "mechanical engineering",
            "civil engineering", "electrical engineering", "electronics engineering",
            "chemical engineering", "biotechnology", "aerospace engineering",
            "data science", "artificial intelligence", "machine learning", "cyber security",
            "department of", "department", "dept of", "dept", "faculty of", "faculty",
            "school of", "university", "college", "institute", "polytechnic", "academy", "campus",
            "marwadi university", "gujarat technological university", "gtu", "mru",
            "lab manual", "laboratory manual", "laboratory", "practical", "experiment",
            "assignment", "exercise", "course", "subject", "syllabus", "curriculum", "index",
            "aim", "objective", "apparatus", "theory", "procedure", "observation",
            "calculation", "result", "conclusion", "discussion", "program", "source code",
            "output", "code", "submission date", "submission", "date", "page", "academic year",
            "semester", "sem", "term", "class", "division", "batch", "signature", "sign",
            "remark", "grade", "marks", "evaluation", "assessment", "teacher", "instructor",
            "professor", "guide", "mentor", "hod", "head of department", "principal", "dean",
            "topic", "title", "author", "authors", "edition", "editions", "published", "publisher",
            "isbn", "issn", "docmorph", "study material", "lecture notes", "reference", "references",
            "bibliography", "citation", "citations", "precaution", "precautions", "conclusion",
            "conclusions", "result", "results", "observation", "observations", "experiment",
            "experiments", "practical", "practicals", "assignment", "assignments", "exercise",
            "exercises", "chapter", "chapters", "section", "sections", "unit", "units",
            "problem", "problems", "solution", "solutions", "figure", "fig.", "table", "chart"
        )

        // Regex patterns for identity pairs
        // 1. Name followed by ID in parentheses or brackets: Vivek Dhedhi (92400120571)
        val PATTERN_BRACKETS = Regex("""^([A-Za-z\s.'-]+?)\s*(?:\(([A-Za-z0-9_/\-]+)\)|\[([A-Za-z0-9_/\-]+)\])""")
        // 2. Name followed by delimiter: Vivek Dhedhi - 92400120571
        val PATTERN_DELIMITER = Regex("""^([A-Za-z\s.'-]+?)\s*[-–—|,/]\s*([A-Za-z0-9_/\-]+)""")
        // 3. ID followed by delimiter and Name: 92400120571 - Vivek Dhedhi
        val PATTERN_INVERTED = Regex("""^([A-Za-z0-9_/\-]+)\s*[-–—|,/]\s*([A-Za-z\s.'-]+)""")
        // 4. Bracketed ID followed by Name: (92400120571) Vivek Dhedhi
        val PATTERN_BRACKETED_INVERTED = Regex("""^(?:\(([A-Za-z0-9_/\-]+)\)|\[([A-Za-z0-9_/\-]+)\])\s*([A-Za-z\s.'-]+)""")
        // 5. Name followed by digits: Vivek Dhedhi 92400120571
        val PATTERN_WHITESPACE = Regex("""^([A-Za-z\s.'-]+?)\s{1,4}(\d{6,16})(?:\s+|$)""")

        // Standalone page number pattern to strictly exclude: "Page 1 of 10", "1 / 5", "Page 2"
        val PAGE_NUMBER_REGEX = Regex("""(?i)^(page\s*\d+(\s*of\s*\d+)?|\d+\s*/\s*\d+|\d{1,3})$""")
    }

    fun isAcademicTerm(text: String): Boolean {
        val norm = text.lowercase().trim()
        if (ACADEMIC_STOP_WORDS.contains(norm)) return true
        for (stop in ACADEMIC_STOP_WORDS) {
            if (stop.contains(" ") && norm.contains(stop)) return true
            if (!stop.contains(" ") && Regex("""\b${Regex.escape(stop)}\b""").containsMatchIn(norm)) return true
        }
        return false
    }

    fun isValidStudentName(nameCandidate: String): Boolean {
        val clean = nameCandidate.trim()
        if (clean.length < 2 || clean.length > 45) return false
        if (clean.any { it.isDigit() }) return false
        if (!clean.matches(Regex("""^[A-Za-z\s.'-]+$"""))) return false
        if (isAcademicTerm(clean)) return false

        val tokens = clean.split(Regex("""[\s.\-]+""")).filter { it.isNotEmpty() }
        if (tokens.size < 2 || tokens.size > 5) return false
        return true
    }

    fun isPageNumberText(text: String): Boolean {
        val clean = text.trim()
        if (clean.isEmpty()) return false
        if (Regex("""(?i)\b(?:page|pg\.?)\s*\d+""").containsMatchIn(clean)) return true
        if (Regex("""(?i)\b\d+\s*(?:of|/)\s*\d+\b""").containsMatchIn(clean)) return true
        if (Regex("""^[\-–—]\s*\d+\s*[\-–—]$""").matches(clean)) return true
        val num = clean.toIntOrNull()
        if (num != null && num in 1..200) return true
        return false
    }

    fun classifyIdentifier(idCandidate: String): String? {
        val trimmed = idCandidate.trim()
        if (trimmed.isEmpty()) return null

        if (isPageNumberText(trimmed)) {
            return null
        }

        val clean = trimmed.filter { it !in "()[]-–—|,;:# " }.trim()
        if (clean.isEmpty()) return null

        if (clean.all { it.isDigit() } && clean.length in 6..18) {
            return "enrollment_number"
        }
        if (clean.all { it.isDigit() } && clean.length in 1..4) {
            val num = clean.toIntOrNull()
            if (num != null && num in 1..200) return null
            return "roll_number"
        }
        if (clean.matches(Regex("""^(?i)[A-Z0-9\-_]{5,20}$""")) && clean.any { it.isDigit() }) {
            return "student_id"
        }
        return null
    }

    fun detectUnlabelledPairs(blocks: List<NativeTextBlock>): List<IdentityMatch> {
        val matches = mutableListOf<IdentityMatch>()

        for (block in blocks) {
            val text = block.text.trim()
            if (PAGE_NUMBER_REGEX.matches(text)) continue

            // 1. Bracket pattern: Name (ID) or Name [ID]
            var m = PATTERN_BRACKETS.find(text)
            if (m != null) {
                val namePart = m.groupValues[1]
                val idPart = if (m.groupValues[2].isNotEmpty()) m.groupValues[2] else m.groupValues[3]
                val idType = classifyIdentifier(idPart)
                if (isValidStudentName(namePart) && idType != null) {
                    val pairId = UUID.randomUUID().toString()
                    matches.add(createMatch(namePart, idPart, idType, pairId, false, block, 0.95f))
                    continue
                }
            }

            // 2. Delimiter pattern: Name - ID
            m = PATTERN_DELIMITER.find(text)
            if (m != null) {
                val namePart = m.groupValues[1]
                val idPart = m.groupValues[2]
                val idType = classifyIdentifier(idPart)
                if (isValidStudentName(namePart) && idType != null) {
                    val pairId = UUID.randomUUID().toString()
                    matches.add(createMatch(namePart, idPart, idType, pairId, false, block, 0.92f))
                    continue
                }
            }

            // 3. Inverted delimiter pattern: ID - Name
            m = PATTERN_INVERTED.find(text)
            if (m != null) {
                val idPart = m.groupValues[1]
                val namePart = m.groupValues[2]
                val idType = classifyIdentifier(idPart)
                if (isValidStudentName(namePart) && idType != null) {
                    val pairId = UUID.randomUUID().toString()
                    matches.add(createMatch(namePart, idPart, idType, pairId, true, block, 0.90f))
                    continue
                }
            }

            // 4. Inverted bracket: (ID) Name or [ID] Name
            m = PATTERN_BRACKETED_INVERTED.find(text)
            if (m != null) {
                val idPart = if (m.groupValues[1].isNotEmpty()) m.groupValues[1] else m.groupValues[2]
                val namePart = m.groupValues[3]
                val idType = classifyIdentifier(idPart)
                if (isValidStudentName(namePart) && idType != null) {
                    val pairId = UUID.randomUUID().toString()
                    matches.add(createMatch(namePart, idPart, idType, pairId, true, block, 0.90f))
                    continue
                }
            }

            // 5. Whitespace pattern: Name 92400120571
            m = PATTERN_WHITESPACE.find(text)
            if (m != null) {
                val namePart = m.groupValues[1]
                val idPart = m.groupValues[2]
                val idType = classifyIdentifier(idPart)
                if (isValidStudentName(namePart) && idType != null) {
                    val pairId = UUID.randomUUID().toString()
                    matches.add(createMatch(namePart, idPart, idType, pairId, false, block, 0.88f))
                    continue
                }
            }
        }

        return matches
    }

    private fun createMatch(
        name: String,
        id: String,
        idType: String,
        pairId: String,
        isInverted: Boolean,
        sourceBlock: NativeTextBlock,
        confidence: Float
    ): IdentityMatch {
        return IdentityMatch(
            name = name.trim(),
            identifier = id.trim(),
            identifierType = idType,
            pairId = pairId,
            isInverted = isInverted,
            nameBlock = sourceBlock,
            idBlock = sourceBlock,
            confidence = confidence
        )
    }
}
