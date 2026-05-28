import { describe, expect, it } from "vitest";
import { orderUniverseHoldingsFirst } from "./freeTierUniverse";

describe("orderUniverseHoldingsFirst", () => {
  it("prioritizes leadership names ahead of defensive macro names under capped scans", () => {
    const rows = [
      {
        id: "1",
        ticker: "IEF",
        segmentKey: "macro",
        name: "IEF",
        createdAt: new Date(),
        updatedAt: new Date(),
        assetType: "etf",
        exchange: "US",
        isActive: true,
        dataProviderSymbol: "IEF",
      },
      {
        id: "2",
        ticker: "JO",
        segmentKey: "agriculture",
        name: "JO",
        createdAt: new Date(),
        updatedAt: new Date(),
        assetType: "etf",
        exchange: "US",
        isActive: true,
        dataProviderSymbol: "JO",
      },
      {
        id: "3",
        ticker: "SNOW",
        segmentKey: "software_cloud",
        name: "SNOW",
        createdAt: new Date(),
        updatedAt: new Date(),
        assetType: "equity",
        exchange: "US",
        isActive: true,
        dataProviderSymbol: "SNOW",
      },
      {
        id: "4",
        ticker: "MSFT",
        segmentKey: "equities_core",
        name: "MSFT",
        createdAt: new Date(),
        updatedAt: new Date(),
        assetType: "equity",
        exchange: "US",
        isActive: true,
        dataProviderSymbol: "MSFT",
      },
    ];

    const ordered = orderUniverseHoldingsFirst(rows, new Set<string>());
    expect(ordered.map((r) => r.ticker)).toEqual(["SNOW", "MSFT", "JO", "IEF"]);
  });
});
