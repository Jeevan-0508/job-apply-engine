def tailor_lines(lines, jd_signal):
    scored = []

    for line in lines:
        score = 0
        l = line.lower()

        for skill, weight in jd_signal.items():
            if skill in l:
                score += weight

        if score > 0:
            scored.append((score, line))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [line for score, line in scored]
