// Usage: node fetch_schema.mjs <out.graphql>
import { getIntrospectionQuery, buildClientSchema, printSchema } from "graphql";
import { writeFileSync } from "node:fs";

const res = await fetch("https://api.morpho.org/graphql", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ query: getIntrospectionQuery({ descriptions: true, inputValueDeprecation: true }) }),
});
const json = await res.json();
if (json.errors) throw new Error(JSON.stringify(json.errors));
writeFileSync(process.argv[2], printSchema(buildClientSchema(json.data)) + "\n");
