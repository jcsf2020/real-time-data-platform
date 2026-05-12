-- Override dbt's default schema naming so that +schema: silver produces "silver",
-- not "<default_schema>_silver". Without this macro, dbt would prefix every custom
-- schema with the profile's default schema (e.g. "public_silver").
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
