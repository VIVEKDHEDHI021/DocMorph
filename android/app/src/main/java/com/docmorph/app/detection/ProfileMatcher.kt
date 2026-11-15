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

        return candidates.map { cand ->
            val repl = when (cand.fieldType) {
                "student_name" -> fullName
                "enrollment_number" -> enrollmentNumber
                "roll_number" -> rollNumber
                "student_id" -> studentId
                else -> null
            }
            cand.copy(replacementText = repl)
        }
    }
}

