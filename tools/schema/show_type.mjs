// Usage: node show_type.mjs <schema.graphql> Type[.field] ...  — prints fields compactly (no descriptions)
import { buildSchema } from "graphql";
import { readFileSync } from "node:fs";

const schema = buildSchema(readFileSync(process.argv[2], "utf8"));
for (const arg of process.argv.slice(3)) {
  const [typeName, fieldName] = arg.split(".");
  const t = schema.getType(typeName);
  if (!t) { console.log(`?? ${typeName}`); continue; }
  if (t.getValues) { console.log(`enum ${typeName}: ${t.getValues().map(v => v.name).join(" ")}`); continue; }
  if (t.getTypes) { console.log(`union ${typeName} = ${t.getTypes().map(v => v.name).join(" | ")}`); continue; }
  if (!t.getFields) { console.log(`scalar ${typeName}`); continue; }
  console.log(`${typeName} {`);
  for (const f of Object.values(t.getFields())) {
    if (fieldName && f.name !== fieldName) continue;
    const args = f.args?.length ? `(${f.args.map(a => `${a.name}: ${a.type}`).join(", ")})` : "";
    console.log(`  ${f.name}${args}: ${f.type}${f.deprecationReason ? "  @deprecated" : ""}`);
  }
  console.log("}");
}
