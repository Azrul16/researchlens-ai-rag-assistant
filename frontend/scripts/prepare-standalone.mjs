import { cpSync, existsSync, mkdirSync } from "node:fs";
import path from "node:path";

const destination = path.resolve(".next/standalone");
if (!existsSync(destination))
  throw new Error("Next.js standalone output is missing.");
mkdirSync(path.join(destination, ".next"), { recursive: true });
cpSync(path.resolve(".next/static"), path.join(destination, ".next/static"), {
  recursive: true,
});
if (existsSync("public"))
  cpSync(path.resolve("public"), path.join(destination, "public"), {
    recursive: true,
  });
