import { NextResponse } from "next/server";
import { readFileSync } from "fs";
import path from "path";

export async function GET() {
  const data = JSON.parse(readFileSync(path.join(process.cwd(), "public/simulate.json"), "utf8"));
  return NextResponse.json(data);
}
