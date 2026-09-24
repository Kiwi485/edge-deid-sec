# Study 4: Residual Identity-Cue Evaluation

## Scope and threat model

The adversary receives only the transmitted de-identified output and may try to infer identity-relevant information from residual non-tongue anatomical content. The evaluation measures region-selective content removal and manually observable residual cues. It does not establish formal anonymization, unlinkability, or resistance to re-identification attacks. Non-Tongue Removal Rate, Residual Non-Tongue Pixel Ratio, Output Contamination, and Tongue Region Completeness are therefore pixel-level privacy proxies, not proof of anonymity.

## Predefined cue categories

| Cue | Operational definition |
|---|---|
| Teeth | Natural or artificial tooth structure, including a visible tooth edge. |
| Braces or dental hardware | Braces, wires, brackets, retainers, fillings, or other dental hardware. |
| Lip tissue or contour | Lip tissue or a recognizable lip boundary/contour. |
| Facial skin | Non-lip facial skin, including visible texture or pigmentation. |
| Facial or jaw contour | A recognizable facial, cheek, chin, or jaw outline. |
| Distinctive marker | A scar, mole, tattoo, lesion, or other potentially distinctive marker. |
| Other | Any other visible non-tongue content that could plausibly carry identity information. |

Scores were assigned independently for each category: 0 = not visible, 1 = possibly visible but unclear or extremely small, and 2 = clearly visible. Scores 1 and 2 count as residual cues in the binary report; score 2 is also reported separately.

## Procedure

All 15 outputs in the fixed primary test split (`split_manifest.json`, seed 42) were generated from the validation-selected U-Net + MobileNetV2 checkpoint at a fixed 0.5 threshold. Files were assigned anonymous IDs E01-E15 and reviewed at a consistent contact-sheet scale, followed by native-resolution inspection. One human reviewer supplied the final scores; AI assistance was used to prepare the protocol, generate the review materials, and aggregate the scores. The completed annotation sheet is in [rq4_residual_identity_cue_annotations.csv](rq4_residual_identity_cue_annotations.csv).

This was a preliminary manual audit by one human reviewer. The observations have not yet been independently replicated or adjudicated, so no inter-rater agreement is reported. The provided tooling supports separate reviewer sheets and reports exact agreement and Cohen's kappa when a second review becomes available.

## Results

<!-- The table below is generated from the annotation CSV. -->

| Residual identity cue | Any residual cases | Clearly visible cases | Rate of any residual cue |
|---|---:|---:|---:|
| Teeth | 10 / 15 | 7 / 15 | 66.7% |
| Braces or dental hardware | 1 / 15 | 1 / 15 | 6.7% |
| Lip tissue or contour | 7 / 15 | 3 / 15 | 46.7% |
| Facial skin | 12 / 15 | 9 / 15 | 80.0% |
| Facial or jaw contour | 0 / 15 | 0 / 15 | 0.0% |
| Distinctive marker | 0 / 15 | 0 / 15 | 0.0% |
| Other | 1 / 15 | 0 / 15 | 6.7% |
| Any identity-relevant cue | 15 / 15 | 13 / 15 | 100.0% |

## Qualitative failure example

E09 is the clearest failure example: teeth, lip tissue, and facial skin remain clearly visible in the transmitted output (all scored 2). E01 also retains teeth and dental hardware. Across the audit, facial skin was often retained where the predicted tongue mask extended beyond the tongue tip into the tissue below it. These examples show why a small residual pixel area cannot be treated as evidence that identity-relevant information has been removed. The review images and contact sheet remain under `outputs/acm_paper/rq4/audit_images/` and are intentionally excluded from version control because they contain anatomical imagery.

## Revised privacy claim

The pipeline removes most pixels outside the predicted tongue region and substantially reduces visible facial context in the evaluated images. However, the single-reviewer audit found at least one possible residual identity-relevant cue in every evaluated output, including teeth, lip tissue, dental hardware, and facial skin. The facial-skin failures were commonly associated with the predicted tongue mask extending below the tongue tip. The reported pixel metrics quantify region-selective removal; they do not guarantee anonymity or the absence of identity-relevant information.

## Mitigation and limitations

Potential controls include a validated conservative tongue mask, small inward mask erosion, rejection or reprocessing of uncertain predictions, and explicit detection of teeth, lips, or skin. Any such control must be evaluated against tongue completeness so that diagnostically relevant tongue-tip and tongue-edge content is not removed.

This audit is limited to 15 images from one fixed split and one annotator. It evaluates visible predefined cues, not actual recognition or linkage attacks, demographic generalization, temporal linkage, or latent biometric information within the tongue itself. A second independent review and evaluation on a larger subject-separated test set are needed before making broader privacy claims.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -m experiments.acm_paper.rq4_privacy_evaluation.generate_audit_outputs

.\.venv\Scripts\python.exe -m experiments.acm_paper.rq4_privacy_evaluation.residual_identity_audit summarize `
  --annotations docs\acm_paper\rq4_residual_identity_cue_annotations.csv `
  --markdown outputs\acm_paper\rq4\residual_identity_cue_summary.md `
  --json outputs\acm_paper\rq4\residual_identity_cue_summary.json
```

To create a blank sheet for an independent second reviewer:

```powershell
.\.venv\Scripts\python.exe -m experiments.acm_paper.rq4_privacy_evaluation.residual_identity_audit init `
  --output outputs\acm_paper\rq4\reviewer_b.csv
```
