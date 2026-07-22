# Outline: Marrow — short pitch deck

A 5-slide pitch deck for Marrow, a CLI that maps a repo's tests to the code they actually cover.
One idea per slide.

1. **Title** — "Marrow" / subtitle: "Know what your tests actually cover."
2. **The problem** — "Big test suites hide their gaps." Large suites are slow and nobody knows which
   tests cover which code, so dead tests linger and real gaps go unnoticed.
3. **The idea** — "Watch one run. Draw the real map." Marrow instruments a single test run and
   produces a test→code coverage map — no annotations, no config.
4. **How it works** — three steps: run `marrow watch -- <your test cmd>`; Marrow records which lines
   each test exercised; it emits an interactive map plus a list of dead tests and untested lines.
5. **Call to action** — "Install Marrow" / `pipx install marrow` / "Works with pytest, Jest, go test."
