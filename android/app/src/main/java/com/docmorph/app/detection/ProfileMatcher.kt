package com.docmorph.app.detection

class ProfileMatcher {

    /**
     * Re-matches detection candidates with a student profile.
     */
    fun matchCandidates(
        candidates: List<DetectionCandidate>,
        profile: Map<String, String?>?
    ): List<DetectionCandidate> {
        if (profile == null) return candidates

        val fullName = profile["fullName"]
        val enrollmentNumber = profile["enrollmentNumber"]
        val rollNumber = profile["rollNumber"]
        val studentId = profile["studentId"]
        val fallbackId = if (!studentId.isNullOrBlank()) studentId else if (!enrollmentNumber.isNullOrBlank()) enrollmentNumber else rollNumber
        val fallbackRoll = if (!rollNumber.isNullOrBlank()) rollNumber else if (!enrollmentNumber.isNullOrBlank()) enrollmentNumber else studentId
        val fallbackEnroll = if (!enrollmentNumber.isNullOrBlank()) enrollmentNumber else if (!studentId.isNullOrBlank()) studentId else rollNumber

        return candidates.map { cand ->
            val repl = when (cand.fieldType) {
                "student_name" -> fullName
                "enrollment_number" -> fallbackEnroll
                "roll_number" -> fallbackRoll
                "student_id" -> fallbackId
                else -> fallbackId
            }
            cand.copy(replacementText = repl)
        }
    }
}

