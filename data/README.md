# Example data

`O.xlsx` is the example age-value input used by the supplied configurations.

`CENOGRID_benthic_d18O_sampling_density.xlsx` is the full age-value input used
for the manuscript sampling-density sensitivity experiment. It contains the
Cenozoic benthic oxygen-isotope series prepared from CENOGRID and is read by
`run_sampling_density_analysis.py`.

Required columns:

| Column | Description |
|---|---|
| `Age` | Age in kyr |
| `Value` | Continuous proxy value |

Replace the file or update `input.file`, `input.age_column`, and
`input.value_column` in the YAML configuration before analysing another record.

When reusing the CENOGRID-derived input, cite the original CENOGRID data source.
The repository MIT License applies to the software and does not replace the
terms or citation requirements of third-party source data.
