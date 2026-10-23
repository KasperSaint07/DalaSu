# 04. Comparison with Existing Systems

Source verification date: 21.10.2026.
Document rule: every fact has a link to a source. If there is no source, the fact is marked "not confirmed" and is not used in the conclusions. Prices without a source have been removed.

## 1. Systems Compared

| System | What it is | Sources |
|---|---|---|
| CropX | In-field soil moisture sensors + paid software with irrigation recommendations | [1][2][3] |
| IrriWatch (Hydrosat) | Satellite service based on thermal imagery: ET, soil moisture, irrigation plan | [4][5][6][7] |
| Egistic | Kazakhstani satellite field monitoring and farm management (vegetation, nitrogen, chlorophyll, moisture, telematics) | [8][9][10][20] |
| AgroData (Kazhydromet) | Free state web app for Kazakhstani farmers: agrometeorological data, soil moisture forecast, crop model | [18][19] |
| TOMCHI | Free mobile app of Uzbekistan about water-saving irrigation technologies | [11][12] |
| DalaSu | FAO-56 + ML calibration, no sensors, for small farms (project) | project docs |

## 2. Comparison Table

| Criterion | CropX | IrriWatch | Egistic | AgroData | TOMCHI | DalaSu |
|---|---|---|---|---|---|---|
| Core approach | Soil sensors + software; the platform uses weather and calculated ET [1][3] | Thermal satellite imagery, ET and soil moisture calculation [4][5]; coupled with a soil water balance model based on meteorological data [14] | Satellite imagery, vegetation, nitrogen, chlorophyll and moisture indices [9][20] | Data from the state observation network (226 agrometeorological stations), satellite imagery; since 2021 the DSSAT crop model [18][19] | Reference information on irrigation technologies and calculation of their benefits [11] | FAO-56 water balance + ML correction from Sentinel-2 NDVI |
| Field sensors required | Yes [1] | No, "without any field sensors" [6] | No (satellite) [9] | No farmer-side sensors; uses the state station network [19] | No [11] | No |
| Recommendation of irrigation timing and volume | Yes: when and how much water is needed [3] | Yes: 7-day planner, optimal day and water amount [7]; daily analytics on irrigation needs [15] | Not stated in the sources found; monitoring, farm activity planning, telematics, marketplace and agro-consulting are stated [9][20] | Partly: recommended sowing dates and soil moisture reserve forecast; the DSSAT model determines the optimal number of irrigations [18]. Whether a per-field irrigation schedule is available in the app is not confirmed | No: the app provides information and calculates the effect of technologies, not an irrigation schedule [11] | Yes (product goal) |
| Target user | Farms of any size, per the company [3] | Farmers of various sizes, also government bodies and agribusiness [5][7] | Stated aim: small and medium farms [10]; in the May 2021 article the monitored land is predominantly grain and oilseeds in the north, east and west [9] | Farmers and peasant farms [18] | Smallholder, medium and large farms, academia and advisors in Uzbekistan; main users are farmers [11] | Small farms in southern Kazakhstan |
| Payment model | Hardware + annual subscription [1][2][3] | Subscription [4][6] | Per-hectare fee, per the company's project manager (2021) [10] | Free [18] | Free [11] | Goal: free or almost free |
| Cost (public data) | Sensor ≈ $595–695, subscription ≈ $300 per year per sensor (aggregators, verify against the CropX store) [1][2]; in 2018: $600–899 per sensor, subscription from $275 [3] | Price not found, not stated | 90 tenge per hectare versus up to 600 tenge at competitors, company statement from 2021 (current price not verified) [10] | $0 [18] | $0 [11] | Not defined |
| Geography | International, dealers in Australia [13] | About 60 countries at the time of the 2023 merger [4]; Hydrosat itself states 43 countries in 2024 [7]; Africa, Latin America [6][7] | Kazakhstan, over 1 million ha [8][9], predominantly north, east and west [9]; also users in Russia and Uzbekistan per the app listing [20] | Kazakhstan [18][19] | Uzbekistan [11] | Kazakhstan |
| Status | Active (store, 2026 prices) [1] | Active, a Hydrosat product, 2026 publications [4][14] | **Operating, closure not confirmed.** Registry status "active"; app last updated 27.02.2025 [20][21]. Warning signs: the estimated revenue of the LLP fell from 912 million tenge (2024) to 14.6 million (2025), and the registry page shows one unexplained risk flag about cessation or deregistration [21] | Active: described by UN ESCAP on 19.10.2026 [19] | Active per the FAO catalog; date of last update not found [11] | In development |

## 3. Verification of Claims from the Project

| Claim in the project | Result | Source |
|---|---|---|
| CropX: "$300–700 per field" | **Corrected.** Actual model: sensor + annual subscription for each sensor. It cannot be reduced to "per field" | [1][2][3] |
| IrriWatch: "works in 57 countries" | **Not confirmed.** Sources give "about 60 countries" (NASA, 2023) and "43 countries" (Hydrosat, 2024). State the range with dates | [4][7] |
| IrriWatch: "acquired by Hydrosat" | Confirmed, June 2023 | [4][5] |
| IrriWatch: "corporate subscription, not for small farms" | **Partially.** Subscription confirmed. The claim "not for small farms" is not confirmed: the company states a goal of serving "growers of all sizes" | [4][7] |
| Egistic: "more than 130 farms" | **Not confirmed.** Found: "over 1 million ha" (May 2021) and "over 700,000 ha and over 1,000 registered users" (June 2021); the Google Play listing repeats "1000 registered users" | [8][9][10][20] |
| Egistic: "per-hectare fee" | **Confirmed.** In 2021 the company's project manager gave a price of 90 tenge per hectare versus up to 600 tenge at competitors. The current price is not verified | [10] |
| Egistic: "oriented to medium and large farms" | **Contradicts the source.** In a 2021 interview the founder speaks of making the product affordable for small and medium farms | [10] |
| Egistic: "closed" | **Not confirmed, evidence points the other way.** Registry status "active", app updated in February 2025. Revenue of the LLP collapsed in 2025, so "closed" cannot be ruled out later, but it cannot be stated now | [20][21] |
| Egistic: "supported by Nazarbayev University" | Partially: graduate of the NU innovation cluster, located in Astana Hub | [16] |
| TOMCHI as an analogue | **Clarified.** It is a reference app, not an irrigation scheduler; not a direct competitor | [11][12] |
| "No free irrigation advisor exists in Kazakhstan" | **Contradicted.** AgroData is a free state service with a soil moisture forecast and a crop model that determines the optimal number of irrigations | [18][19] |

Open question on Egistic: task DAL-14 says the status "closed" must be reflected. The sources found do not support it. The acceptance line should be changed to "Egistic status reflected as it is: operating, with a sharp revenue drop of the LLP in 2025". If the team has a document proving closure (news, letter, registry extract), it should be added as a source and the "Status" row replaced.

## 4. Conclusion

### How DalaSu differs

1. **No sensors.** CropX requires in-field hardware and charges an annual subscription for each sensor [1][2]. DalaSu has no hardware costs.
2. **Direct irrigation recommendation for a specific field.** IrriWatch provides an irrigation plan, but we found no information on a focus on Central Asia [7]. TOMCHI provides only reference information [11]. For Egistic, irrigation recommendations are not stated in the sources [9][20]. AgroData provides a soil moisture forecast and a crop model [18], but a per-field irrigation schedule for a small farm is not confirmed.
3. **Explainability.** The FAO-56 calculation is transparent to an agronomist: ML is only a correction on top of the physical balance, and the method relies on an open standard. The sources found contain no data on the transparency of competitors' algorithms, so we make no direct comparison on this point.
4. **Price.** The target model is free or almost free. A price comparison is valid for CropX [1][2], TOMCHI [11], AgroData [18] and, with a 2021 date, Egistic (90 tenge per hectare) [10]. Both AgroData and Egistic position themselves as low-cost or free, so DalaSu cannot claim to be the only affordable option in Kazakhstan.

### Where DalaSu is inferior

1. **Accuracy.** IrriWatch uses thermal satellite land surface temperature data, which we do not have; we rely on weather and NDVI [6][14]. No quantitative accuracy comparison has been performed.
2. **Direct soil moisture measurement.** CropX measures soil moisture on site [1]; in DalaSu it is calculated by the water balance, and errors accumulate.
3. **Maturity and coverage.** IrriWatch operates in dozens of countries with a corporate team [4], Egistic covers over 1 million ha [9], AgroData relies on 226 state stations [19]. DalaSu does not yet have a pilot field in Kazakhstan.
4. **Validation.** Quantitative validation only on US-Ne2, only qualitative for Kazakhstan. This is a methodological limitation.
5. **Data.** Sentinel-2 delay and cloud cover; when there is no image, only the physical calculation works.
6. **Official data.** AgroData is built on the state observation network, which a student project cannot match in weather data quality.

### Positioning in one sentence

DalaSu does not compete on accuracy with sensor-based and thermal satellite systems, and it is not the only free tool in Kazakhstan; its niche is an explainable, field-level irrigation recommendation (when and how much) for small farms, which the sources found do not confirm for AgroData or Egistic. The claim "the niche is free" must be worded as "not confirmed to be occupied" and re-checked against the AgroData app itself, which could not be opened automatically.

## Sources

1. fitgap, CropX (CropX store prices, 2026): https://us.fitgap.com/products/021310/cropx
2. rfp.wiki, CropX (sensor and subscription price): https://www.rfp.wiki/specialty-industries/agriculture-software/conservis/cropx
3. eeNews Europe, CropX, 2018 prices (published 1 May 2018): https://www.eenewseurope.com/news/smart-farming-platform-makes-connected-soil-reality
4. NASA Spinoff, IrriWatch and Hydrosat: https://spinoff.nasa.gov/node/11489
5. Payload, Hydrosat acquires IrriWatch: https://payloadspace.com/hydrosat-acquires-irriwatch
6. NABC, IrriWatch description (no field sensors, 10 m resolution): https://nabc.nl/member/hydrosat-previously-irriwatch/
7. Hydrosat, 2024 press release (7-day irrigation planner, 43 countries): https://kitchensinq.q4web.com/investors/news/press-release-details/2024/Hydrosat-Expands-Presence-in-Latin-America-to-Drive-Digital-Agriculture-Innovation/default.aspx
8. Forbes.kz, Egistic and Planet (4 May 2021): https://forbes.kz/news/newsid_249236
9. The Astana Times, Egistic (7 May 2021): https://astanatimes.com/2021/05/kazakh-startup-egistic-provides-daily-satellite-imagery-for-local-farmers/
10. World-NAN, interview with the founder of Egistic (2 June 2021): https://world-nan.kz/en/blogs/kazakhstanskiyi-startap-egistis-pomogaet-otechestvennym-fermeram-povysit-urozhayinost
11. FAO Agritech Observatory, TOMCHI: https://agritechobservatory.review.fao.org/fr/tomchi
12. UzDaily, TOMCHI contest (2019): https://www.uzdaily.uz/en/the-winners-of-the-first-tomchi-contest-announced/
13. NSW DPI AgTech, CropX Australia: https://www.agtech.dpi.nsw.gov.au/collections/soil-moisture/subscription-required_yes?page=2
14. EGU 2026, Hydrosat (abstract EGU26-20878): https://meetingorganizer.copernicus.org/EGU26/EGU26-20878.html?pdf
15. Space Agency Luxembourg, Hydrosat (IrriWatch platform and API, daily irrigation analytics, 120+ crop types; page updated 24.04.2026): https://space-agency.public.lu/en/space-directory/hydrosat.html
16. Startups Magazine, Kazakhstan ecosystem (Egistic, 2 Nov 2021): https://startupsmagazine.co.uk/article-kazakhstans-established-innovation-ecosystem-leads-thriving-startup-scene
17. Tracxn, agritech startups in Kazakhstan (Egistic, grant 26.01.2023; seen only in a search snippet, the site blocks automated access): https://tracxn.com/d/explore/agritech-startups-in-kazakhstan/__R7Goxl_PZW5pPOFh2nTxcs7AMKHzH7hHg3unPNy1S1Y#top-companies
18. Kazhydromet, presentation of the AgroData web application for farmers (11.05.2021): https://www.kazhydromet.kz/ru/post/853
19. UN ESCAP, Satellite Solutions for Food Security (19.10.2026): https://www.unescap.org/blog/satellite-solutions-food-security
20. Google Play, Egistic app (last update 27.02.2025, 10k+ downloads): https://play.google.com/store/apps/details?id=com.egistic.development.egistic_mobile&hl=ru
21. Statsnet, TOO EGISTIC (registry status, revenue 2018–2025, risk flag): https://statsnet.co/companies/kz/31479549
