# Phase 2 brief: Pipeline Presentation (weeks 5–7)

Transcribed from the organizers' brief ("Phase 2: Pipeline Presentation" and "Basic Databricks GitHub Repository Template", both by Bruno Chavez, received Oct 13, 2026). Presentation date and format were not announced; we present **Thu Oct 29, 2026**.

## Objective

Teams develop and present the Databricks pipeline they built from week 5 through week 7, explaining the job design, data flow, transformations, pipeline orchestration, data quality checks, and the value of the final tables or datasets. The work should show that the team can **build, explain, validate and interpret an end-to-end data workflow**, connecting the pipeline design to the resulting analysis: not only working code, but the decisions behind it and the value of the processed data.

## Deliverables

1. **GitHub repository:** complete, organized repo with notebooks, source files, documentation, configuration and the instructions needed to understand or run the project.
2. **Pipeline job:** the Databricks job or workflow, including scheduling or triggering approach, task dependencies, and how failures or reruns are handled.
3. **Pipeline overview:** the overall architecture and how data flows from its source to the final output tables.
4. **Transformations and tables:** the main cleaning, preparation, enrichment, aggregation or modeling steps, and the purpose and value of the resulting tables.
5. **Data quality checks:** how the pipeline identifies and handles missing values, duplicates, invalid records, inconsistent formats and other quality issues.
6. **Technical best practices:** where the solution uses or considers streaming, materialized views, liquid clustering, expectations, and engineering best practices for reliable pipelines.
7. **Analysis and business value:** key findings, metrics, trends or comparisons enabled by the final processed dataset.

## Recommended presentation structure

1. Business or analytical objective
2. Source data and architecture
3. Transformations
4. Data quality
5. Final analysis
6. Conclusion (pipeline's value, strongest insight, next steps)

## Rubric (each criterion scored 1–4)

| Criterion | Excellent (4) |
|---|---|
| GitHub Repository & Documentation | Complete, well organized, documented, easy to navigate, clear instructions and supporting files |
| Job & Pipeline Design | Complete, logical Databricks job and pipeline, including task flow, dependencies, and how data moves through each stage |
| Transformations & Table Value | Explains appropriate transformations, their purpose, and the value of the resulting tables for downstream use |
| Streaming, Materialized Views, Liquid Clustering & Expectations | Clearly explains relevant use or evaluation of each, and related reliability / performance choices |
| Data Quality Checks | Thorough checks for missing values, duplicates, invalid records, data types, consistency, expectations and other relevant issues |
| Analysis, Insights & Business Value | Meaningful, accurate findings from the pipeline output with strong evidence, and clearly explains the value of the final tables |
| Technical Communication | Explains technical decisions clearly, connects implementation to outcomes, responds confidently to questions |

Lower levels: Good (3) = mostly complete, minor gaps; Developing (2) = some components, unclear end-to-end; Needs Improvement (1) = missing or unclear.

## Required repository template

```
my-databricks-repo/
├── resources/
│   ├── jobs/
│   │   └── daily_orchestration_job.yml
│   └── pipelines/
│       └── lakeflow_pipeline.yml
└── src/
    └── transformations/
        ├── silver/
        │   ├── st_orders_cleaned.py   # all your tables
        │   └── mv_customer_summary.sql
        └── gold/
            ├── st_daily_revenue.py
            └── mv_executive_kpis.sql
```

- `resources/jobs/`: job definitions, schedules and task orchestration
- `resources/pipelines/`: Lakeflow / Delta Live Tables pipeline configuration
- `src/transformations/silver/`: cleaned and standardized table logic
- `src/transformations/gold/`: business-ready tables, metrics and reporting logic

**How our repo maps to it:** same layout, plus `src/transformations/bronze/` (the raw-ingestion layer of the medallion architecture, which the template does not show), `src/validation/` (the job's quality-gate notebook and the local parity test), `databricks.yml` (required by Asset Bundles to deploy `resources/`), `docs/`, and `phase1_eda/` (Phase 1, archived).

## Course background

Phase 1 included Databricks Academy courses: Databricks Fundamentals, Lakehouse Fundamentals, Analytics Fundamentals, Data Engineering Fundamentals, Data Governance Fundamentals.
