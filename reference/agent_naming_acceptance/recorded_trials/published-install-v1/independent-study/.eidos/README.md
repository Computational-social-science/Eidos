# EIDOS project workspace

Your research files and environment stay in this project. Edit project.yaml to
declare the validator command, required evidence, claim register and document.
The starter validator deliberately refuses acceptance until configured.

Run `eidos check --project ..` from this folder or select the project root from
any directory. `--execution-only` checks the command/output contract without
claiming scientific acceptance. Imported validator helpers and data/configuration
manifests belong in validity_inputs. The validator must verify underlying data
and provenance. `eidos feedback` exports local metadata, never uploads it.
