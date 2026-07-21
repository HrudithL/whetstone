"""Scientific archetype — distilled reference example.

Data: data/reactions.csv  (1,683 atmospheric reactions; rate constants
      of trace gases with OH and three other oxidants, with
      uncertainties)
Story: OH rate constants at 298 K for ten common trace gases, with
       units in the headers, scientific notation, and percent
       uncertainty.
"""
import pandas as pd
from great_tables import GT, html

df = pd.read_csv("data/reactions.csv")

# Curated subset spanning the full reactivity range (10⁻¹⁵ → 10⁻¹⁰), sorted
# slow → fast so the eye walks reactivity in a natural reading order.
picks = ["methane", "benzene", "ethanol", "methanol", "toluene",
         "formaldehyde", "ethene", "acetaldehyde", "propene", "isoprene"]
sub = (
    df[df["cmpd_name"].isin(picks)]
      .loc[:, ["cmpd_name", "cmpd_formula", "cmpd_mwt", "OH_k298", "OH_uncert"]]
      .sort_values("OH_k298")
      .reset_index(drop=True)
)
sub["cmpd_name"] = sub["cmpd_name"].str.capitalize()

(
    GT(sub)
    .tab_header(
        title="OH reaction rate constants at 298 K",
        # Units declared once in the subtitle, not on every cell. Standard
        # convention for scientific tables — keeps cells readable.
        subtitle=html(
            "Selected trace gases. k in cm<sup>3</sup>&nbsp;molecule<sup>&minus;1</sup>&nbsp;s<sup>&minus;1</sup>."
        ),
    )
    .cols_label(
        cmpd_name="Compound",
        cmpd_formula="Formula",
        cmpd_mwt=html("M<sub>w</sub> (g mol<sup>&minus;1</sup>)"),
        OH_k298=html("k(298 K)"),
        OH_uncert="Rel. uncert.",
    )
    # fmt_scientific on rate constants — fmt_number(decimals=4) would round
    # 6.36e-15 to 0.0000 and destroy the data. n_sigfig=3 matches source
    # compilation precision.
    .fmt_scientific(columns=["OH_k298"], n_sigfig=3)
    .fmt_number(columns=["cmpd_mwt"], decimals=2)
    # Uncertainty stored as fraction (0.10), shown as percent (10%) — matches
    # the convention of the source compilation.
    .fmt_percent(columns=["OH_uncert"], decimals=0)
    .sub_missing(columns=["OH_uncert"], missing_text="—")
    .cols_align(align="left", columns=["cmpd_name", "cmpd_formula"])
    .cols_align(align="right", columns=["cmpd_mwt", "OH_k298", "OH_uncert"])
    .tab_source_note(
        source_note=html(
            "Source: IUPAC Task Group on Atmospheric Chemical Kinetic Data Evaluation, "
            "compiled in the <code>reactions</code> dataset (Posit / great_tables sample data)."
        )
    )
)
