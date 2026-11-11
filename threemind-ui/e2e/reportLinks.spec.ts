import { test, expect } from "@playwright/test";
import { projectResourceHref } from "../src/v2/reportLinks";

test("report attachments stay within authenticated project resource routes", () => {
  const base = "/api/v2/projects/11111111-1111-4111-8111-111111111111";
  const id = "22222222-2222-4222-8222-222222222222";
  const image = `${base}/note-assets/${id}`;
  const download = `${base}/artifacts/${id}`;
  expect(projectResourceHref(image, base, true)).toBe(image);
  expect(projectResourceHref(image, base.slice("/api/v2".length), true)).toBe(image);
  expect(projectResourceHref(download, base)).toBe(download);
  expect(projectResourceHref(download, base.slice("/api/v2".length))).toBe(download);
  for (const path of [
    download,
    `https://example.test${image}`,
    `//example.test${image}`,
    image.replace("11111111-", "33333333-"),
    image + "?fetch=other",
    image + "/../../secrets",
    `${base}/note-assets/%2e%2e%2fsecrets`,
    "data:image/png;base64,AA==",
    "javascript:alert(1)",
  ]) {
    expect(projectResourceHref(path, base, true)).toBeUndefined();
  }
  expect(projectResourceHref(image)).toBeUndefined();
  expect(
    projectResourceHref(image, "/api/v2/shared/a-token", true),
  ).toBeUndefined();
});
