# 03. Literature Review

## 1. Scope and approach

DalaSu is a proposed decision-support application for small farms in Kazakhstan. Its intended workflow is to estimate crop water use from weather and field information, maintain a root-zone water balance, and present an understandable irrigation date and amount. This review examines twelve scientific articles on evapotranspiration (ET) estimation and machine learning [1–12], focusing on their methods, validation evidence, and implications for the ET estimation component of DalaSu.

This is a focused narrative review, not a systematic review: no reproducible database search, screening log, or protocol is available in the project repository. The studies differ in target (reference ET₀ or actual ET), spatial scale, inputs, validation design, and climate. Their numerical scores must therefore not be ranked as if they came from one common experiment. Conclusions below distinguish what the papers report from what remains untested for DalaSu.

## 2. Critical synthesis

### 2.1 From ET estimation to irrigation advice

In DalaSu's planned workflow, FAO-56 Penman–Monteith provides a physical reference estimate of ET₀. ET₀ represents a standardized reference surface; it is not a direct observation of water use by a particular crop or field. A crop-specific estimate requires additional crop and growth-stage information, while an irrigation date and amount also require rainfall, soil and root-zone storage, irrigation method and efficiency, and a trigger for applying water. An ET model alone cannot establish the appropriate depth of irrigation. This distinction is central to the project design; it is not a result established by the twelve reviewed papers.

The reviewed studies mainly estimate ET or improve ET products; they do not collectively validate a farmer-facing irrigation recommendation. Chen et al. demonstrate an ET and ecosystem-respiration modelling approach [1]. The other reviewed papers likewise focus on estimation, data integration, spatial mapping, or model evaluation rather than farmer-facing irrigation schedules [1–12]. Therefore, DalaSu must evaluate the recommendation step separately; the reviewed ET results alone cannot establish that the application will reduce water use.

### 2.2 Machine learning and hybrid ET estimation

The reviewed papers represent several different modelling tasks. Liu et al. compare six hybrid approaches at 17 cropland eddy-covariance sites: ML estimates stomatal conductance, which enters the Penman–Monteith equation to calculate ET [7]. Across ten input combinations, ANN performed best in their evaluation, while adding more than two remote-sensing variables generally provided limited further improvement. This conductance-learning design differs from directly training RF or XGBoost to predict ET. dos Santos et al. use Sentinel-2 MSI features to predict the ET fraction of a METRIC reference for sugarcane [2]. Ferreira et al. study reference ET₀ across 437 Brazilian weather stations, comparing ML-estimated meteorological inputs to FAO-56, direct ML estimates, and related variants; they report similar performance for multi-task and single-task learning and better results after climate grouping in some scenarios [4]. These are related to DalaSu's weather/ML work, but their targets and regional data differ from the present US-Ne2 comparison.

The hybrid papers also differ in what is learned. Chen et al. (2021) combine eddy-covariance measurements, physical-model output, meteorological forcing, and remote sensing in a deep-learning HPM; soil temperature is used when available [1]. ElGhawi et al. infer stomatal and aerodynamic resistances within a physical ET formulation [3]. Their analysis exposes equifinality: different parameter combinations can reproduce the flux while yielding physically implausible resistances in an insufficiently constrained model. Predictive accuracy alone therefore does not establish physical interpretability. Koppa et al. embed a learned transpiration-stress formulation in GLEAM, a process-based global evaporation model [6]. Improvements are particularly evident for tall vegetation, but training observations are concentrated in North America and Europe, and the stress targets depend partly on empirical transpiration partitioning. These limitations qualify global transfer and crop-field interpretation. Jawad et al. (2025) calculate ET components with a bucket-based Penman–Monteith model and then apply sequential DNN post-processing [5]. Parameter learning, stress modelling, and output post-processing represent different hybrid designs. The verified description of Jawad et al. establishes sequential post-processing; it does not establish that the learning target is an additive residual. DalaSu’s proposed residual learner is a distinct design choice.

Shang et al. (2023) develop two physically constrained hybrid models for satellite-derived ET over the Tibetan Plateau and evaluate them at 28 flux-tower sites, with additional comparisons to physical and pure-ML methods [10]. Their reported results support investigating physical constraints in that domain. They do not establish transfer to southern Kazakhstan: the plateau's high elevation, vegetation patterns, climate, and data regime are different. The same transfer caution applies to studies in Brazil [4], Arizona and the contiguous United States [5, 8], the Heihe River Basin in China [9], the Hai River Basin in China [12], and Florida wetlands [11].

### 2.3 Remote sensing, NDVI, and spatial scale

Remote sensing can add information about vegetation state and spatial heterogeneity, but input availability and interpretation matter. dos Santos et al. use Sentinel-2 MSI bands to estimate a METRIC-derived ET fraction, with Landsat-8 OLI/TIRS providing the reference target in sugarcane fields [2]. The result is not a direct Sentinel-2 measurement of actual ET. Chen et al. use NDVI among several inputs to HPM [1]. Rashid and Tian combine ECOSTRESS, Harmonized Landsat–Sentinel imagery, reanalysis, and flux observations to estimate daily 30 m ET over sites in the contiguous United States [8]. Shang et al.'s DNN-MET merges satellite ET products, eddy-covariance data, and ancillary information over China's Heihe River Basin [9]. These studies illustrate the value of combining inputs, while their sensor combinations and research-site observations exceed what can be assumed available in a low-cost small-farm workflow.

NDVI may help describe canopy development or support an empirically calibrated Kc, but it is not itself a water-use measurement. In the reviewed studies, vegetation information is used as an input or predictor in specific ET modelling settings [1, 2, 8–10, 12]. Those studies do not establish a universal NDVI-to-Kc relationship or a local calibration for Kazakhstan. Optical imagery is also affected by clouds and revisit timing. DalaSu's planned Sentinel-2/NDVI input should therefore be evaluated as an additional signal and should have a documented fallback when a usable recent observation is unavailable.

Spatial validation also has limits. Eddy-covariance towers measure fluxes over a changing footprint rather than a whole farm or satellite pixel [1, 8, 9, 11]. Zhang et al. (2022) explicitly address the mismatch between tower footprints and heterogeneous wetland patches using object-based upscaling in Florida; their site-specific ensemble achieved NSE above 0.75 at the studied sites, while MOD16A2 had NSE below 0.5 for four wetland communities [11]. This is evidence about those wetland sites, not about crop fields in Kazakhstan. It nevertheless reinforces that observed flux data and spatial predictions must be matched carefully.

### 2.4 Irrigation and regional relevance

An ET estimate becomes useful to a farmer only when translated into a field decision. The twelve reviewed ET papers do not establish whether DalaSu's intended inputs and recommendations are usable or adopted by small farms; this requires local requirements gathering and user testing. The reviewed papers also contain no Kazakhstan-specific validation of the proposed DalaSu pipeline. Thus, performance reported at sites in the United States, Brazil, China, or elsewhere must not be presented as evidence of accuracy in Kazakhstan.

## 3. Structured analysis of the twelve reviewed articles

| Ref. | Study domain and target | Data and method | Main reported contribution | Limitations for DalaSu |
|---|---|---|---|---|
| [1] Chen et al. (2021) | Multiple FLUXNET/SNOTEL sites and East River Watershed, western North America; ET and ecosystem respiration | Deep-learning LSTM HPM integrates flux measurements, physical-model output, weather, and remote sensing; temperature, precipitation, radiation, NDVI, and soil temperature when available | Demonstrates a hybrid predictive framework across several site/use cases | Not an irrigation scheduler; site and watershed data are research-grade; mountainous western-US validation does not establish Kazakhstan transfer |
| [2] dos Santos et al. (2022) | Sugarcane fields; predicts ET fraction derived from METRIC | Sentinel-2 MSI spectral features at 10 m and 20 m; Landsat-8 OLI/TIRS used to calculate the METRIC reference target | Shows that optical MSI features can predict a thermal-model-derived ET fraction in the studied crop/site | Predicts a reference-model target rather than independently measured ET; sugarcane and local calibration limit transfer; optical revisit/cloud constraints remain |
| [3] ElGhawi et al. (2023) | ET flux prediction and identifiability of stomatal/aerodynamic resistances | ML learns both resistances within a physical ET formulation; constrained alternatives address parameter ambiguity | Shows that accurate flux predictions can coexist with implausible resistances in an under-constrained hybrid | Equifinality limits physical interpretation; DalaSu needs plausibility checks in addition to prediction-error metrics |
| [4] Ferreira et al. (2022) | 437 weather stations across Brazil; reference ET₀ and missing meteorological variables | FAO-56 with conventional or ML-estimated missing inputs, direct ML, calibration, multi-task/single-task learning, and climate grouping | Reports that several ML/FAO-56 combinations perform similarly and that climatic grouping can improve some results | Brazil-specific climate/station data; ET₀ rather than field actual ET or an irrigation schedule; results depend on missing-input scenario |
| [5] Jawad et al. (2025) | Arizona and 114 AmeriFlux sites across the contiguous US; daily actual ET | Bucket-based Penman–Monteith ET components followed by sequential DNN post-processing; comparison with MODIS, ECOSTRESS, and OpenET | Reports improved ET estimates for its dryland and CONUS evaluation settings | Uses a specific physical structure and MODIS/reanalysis inputs; the verified method description does not establish an additive residual target; no Kazakhstan farm validation |
| [6] Koppa et al. (2022) | Global daily terrestrial evaporation at 0.25° resolution | Learned transpiration stress embedded in GLEAM; 368 retained flux sites and 90 sap-flow sites inform stress modelling; evaluation uses in situ data and satellite proxies | Improves stress and evaporation estimation, with particularly strong gains for tall vegetation | Training coverage favours North America/Europe; partitioning assumptions affect stress targets; coarse grids cannot resolve individual small fields |
| [7] Liu et al. (2021) | 17 cropland EC sites; actual ET | Six ML algorithms estimate stomatal conductance for Penman–Monteith ET; ten meteorological/remote-sensing input combinations | ANN performs best in the study; adding more than two remote-sensing variables generally yields limited extra benefit | Algorithm rankings apply to the tested conductance-learning hybrids and inputs; they do not establish the best direct ET predictor for DalaSu |
| [8] Rashid and Tian (2024) | 145 eddy-covariance sites in contiguous US; daily 30 m ET | PT-JPL with ECOSTRESS, HLS, ERA5-Land/reanalysis and EC measurements; DNN post-processing assessed on held-out sites | Reports improved performance of the post-processed estimates on test sites not used for training | Multi-sensor availability and US site distribution differ from DalaSu; estimates depend on radiation inputs and tower observations |
| [9] Shang et al. (2021), DNN-MET | Heihe River Basin, China; ET product merging/upscaling | DNN integrates satellite-derived ET products, EC observations, and ancillary surface properties; evaluated with 19 EC sites | Reports reduced RMSE relative to eight ET products and retained relative performance with fewer training EC sites | Basin-specific product set and tower network; results over sparse/barren regions were less consistent; not a small-farm irrigation tool |
| [10] Shang et al. (2023) | Tibetan Plateau; satellite-derived regional ET | Two physical/ML hybrids (surface-conductance and soil-evaporation approaches), evaluated against 28 EC sites and physical/pure-ML approaches | Reports improved performance over physical baselines and some advantage over pure ML in data-sparse settings | High-altitude plateau conditions are distinct from Kazakhstan; limited-training-site experiments do not establish robustness to every drought or vegetation regime |
| [11] Zhang et al. (2022) | Five wetland communities in Big Cypress National Preserve, Florida; wetland ET mapping | Object-based ensemble links tower ET, MODIS products, and meteorology | Site-specific ensemble outperformed MOD16A2 in the studied wetland communities; object units address patch/footprint heterogeneity | Subtropical wetlands are unlike agricultural fields; highly site-specific upscaling; not directly useful as an irrigation prescription |
| [12] Zhang et al. (2023) | Hai River Basin, China; actual ET at site and basin scales | Spatial heterogeneity framework/IDSA with remote sensing and four flux towers; RF, gradient-boosting decision tree, and Cubist models by region | Reports better performance than general ML models at site and basin scales; temperature–NDVI interaction improved interpretability | Four-tower regional setting; water-balance basin reference differs from field irrigation outcomes; transfer to Kazakhstan is untested |

The table treats article claims as domain-specific findings. In particular, the Tibetan Plateau study is not used as a proxy for southern Kazakhstan, the wetland study is not treated as an agricultural analogue, and none of the papers is presented as validation of DalaSu.

## 4. Implications for DalaSu and research gap

The following requirements are derived for the project from the reviewed evidence and its limits; they describe planned evaluation and design decisions.

1. **Explicit prediction targets.** The distinction between reference ET₀ [4] and actual ET [7, 8, 12] requires separate interpretation of ET₀, crop ETc, and observed actual ET. DalaSu’s current FAO-56 baseline estimates ET₀, whereas its RF/XGBoost models target observed actual ET. Their comparison measures predictive agreement with that observation series, with this target mismatch stated explicitly.
2. **Comparable evaluation.** Differences among study targets, sites, and inputs prevent direct ranking of published scores. DalaSu will compare candidates on common chronological test dates, keep model fitting within the training period, and report RMSE, MAE, bias, squared Pearson correlation, and NSE. Spatial validation is additionally needed before claims of regional transfer, as illustrated by the held-out-site evaluation in [8].
3. **Planned residual hybrid.** Objective 2 includes a hybrid candidate that learns the difference between observed actual ET and the physical baseline, then adds the predicted correction to the baseline. It will be evaluated alongside FAO-56 and ML-only RF/XGBoost. This candidate is planned; the current trained RF/XGBoost models are ML-only. Because the physical baseline is ET₀, its residual against actual ET includes crop and surface differences as well as model error. Following the identifiability concern in [3], a lower error will not by itself establish a physically meaningful correction.
4. **Separate irrigation evaluation.** The reviewed ET studies do not validate DalaSu’s recommendation step. The proposed application therefore requires explicit crop/stage coefficients, effective rainfall, root-zone storage, irrigation efficiency, and decision thresholds. These are project design requirements. Local field evaluation is needed to assess recommended dates and amounts and any effects on water use or yield.
5. **Measured value of satellite inputs.** The model-derived targets in [2], limited gains from additional features in [7], and multi-sensor requirements in [8, 9] motivate an incremental comparison of Sentinel-2 features against a weather-only baseline. Cloud/revisit gaps require a documented fallback. A crop- and region-specific NDVI-to-Kc calibration remains an unvalidated project assumption.
6. **Transfer and usability.** Regional training coverage [6], heterogeneous tower footprints [11], and limited local sampling [12] motivate independent field validation. US-Ne2 provides one Nebraska-site experiment, not Kazakhstan validation. Interviews and usability tests will separately examine input availability, comprehension of recommendations, language, and connectivity for the intended small-farm users.

The reviewed studies establish approaches to ET estimation, data fusion, and hybrid modelling. Within this corpus, they do not establish a validated, understandable, low-cost ET-to-irrigation workflow for small farms in Kazakhstan. This is an evidence gap for the proposed application, not a claim that no such systems exist elsewhere in the literature. DalaSu’s intended contribution is a reproducible comparison and an irrigation-advice prototype whose local reliability and practical benefits remain to be tested.

## 5. Limitations of this review

This is a focused rather than systematic review. Most reviewed ET studies use flux towers, satellite products, and research-grade inputs in regions outside Kazakhstan. The papers use different targets, scales, and validation procedures, so their error metrics are not directly comparable. Because this review is restricted to the reviewed twelve ET papers, it does not provide a broader literature survey of FAO-56 limitations, crop-coefficient calibration, Central Asian irrigation, or small-farm adoption.

## 6. Metric note for DalaSu

DalaSu’s current comparison reports squared Pearson correlation, r², which measures linear association and can remain high despite systematic bias. Nash–Sutcliffe efficiency evaluates squared prediction error relative to the observed mean:

$$
\mathrm{NSE}=1-\frac{\sum_i(y_i-\hat{y}_i)^2}{\sum_i(y_i-\bar{y})^2}.
$$

On identical observation–prediction pairs, this equals the coefficient of determination defined as 1 − SSE/SST; it generally differs from squared Pearson correlation.

A recalculation using the project’s existing FAO-56 implementation and the 561 valid test observations from 2023–2024 gives the following results. These are project results, separate from the findings of the reviewed publications.

| Metric | FAO-56 ET₀ against observed actual ET |
|---|---:|
| RMSE | 1.6439 mm/day |
| MAE | 1.1133 mm/day |
| Squared Pearson correlation, r² | 0.4736 |
| Mean bias (prediction − observation) | +0.9175 mm/day |
| NSE | −0.02235 |

The slightly negative NSE indicates a greater squared error than predicting the test-set mean observed ET, despite a moderate correlation. Because reference ET₀ is compared with actual ET without a crop coefficient, this result also reflects a target mismatch and cannot isolate error in the FAO-56 equation.

Reproducibility: observations are in `data/processed/test.csv`; predictions use `load_split` and `add_et0` from `src/ml/fao56/baseline.py`, including the existing wind-height conversion. NSE uses the same valid pairs as the other metrics. The discussion supports reporting both association and error-based performance for all planned candidates.

## 7. References

[1] Chen, J., Dafflon, B., Tran, A. P., Falco, N., & Hubbard, S. S. (2021). A deep learning hybrid predictive modeling (HPM) approach for estimating evapotranspiration and ecosystem respiration. *Hydrology and Earth System Sciences, 25*(11), 6041–6066. https://doi.org/10.5194/hess-25-6041-2021

[2] dos Santos, R. A., Mantovani, E. C., Fernandes-Filho, E. I., Filgueiras, R., Lourenço, R. D. S., Bufon, V. B., & Neale, C. M. U. (2022). Modeling actual evapotranspiration with MSI-Sentinel images and machine learning algorithms. *Atmosphere, 13*(9), 1518. https://doi.org/10.3390/atmos13091518

[3] ElGhawi, R., Kraft, B., Reimers, C., Reichstein, M., Körner, M., Gentine, P., & Winkler, A. J. (2023). Hybrid modeling of evapotranspiration: Inferring stomatal and aerodynamic resistances using combined physics-based and machine learning. *Environmental Research Letters, 18*(3), 034039. https://doi.org/10.1088/1748-9326/acbbe0

[4] Ferreira, L. B., da Cunha, F. F., & Fernandes Filho, E. I. (2022). Exploring machine learning and multi-task learning to estimate meteorological data and reference evapotranspiration across Brazil. *Agricultural Water Management, 259*, 107281. https://doi.org/10.1016/j.agwat.2021.107281

[5] Jawad, M., Behrangi, A., Farmani, M. A., Qiu, Y., Sohi, H. Y., Gupta, A., & Niu, G. Y. (2025). Improved evapotranspiration estimation using the Penman–Monteith equation with a deep learning (DNN) model over the dry southwestern US: Comparison with ECOSTRESS, MODIS, and OpenET. *Journal of Hydrology, 660*, 133460. https://doi.org/10.1016/j.jhydrol.2025.133460

[6] Koppa, A., Rains, D., Hulsman, P., Poyatos, R., & Miralles, D. G. (2022). A deep learning-based hybrid model of global terrestrial evaporation. *Nature Communications, 13*, 1912. https://doi.org/10.1038/s41467-022-29543-7

[7] Liu, Y., Zhang, S., Zhang, J., Tang, L., & Bai, Y. (2021). Assessment and comparison of six machine learning models in estimating evapotranspiration over croplands using remote sensing and meteorological factors. *Remote Sensing, 13*(19), 3838. https://doi.org/10.3390/rs13193838

[8] Rashid, T., & Tian, D. (2024). Improved 30-m evapotranspiration estimates over 145 eddy covariance sites in the contiguous United States: The role of ECOSTRESS, Harmonized Landsat Sentinel-2 imagery, climate reanalysis, and deep neural network postprocessing. *Water Resources Research, 60*(4), e2023WR036313. https://doi.org/10.1029/2023WR036313

[9] Shang, K., Yao, Y., Liang, S., Zhang, Y., Fisher, J. B., Chen, J., Liu, S., Xu, Z., Zhang, Y., Jia, K., Zhang, X., Yang, J., Bei, X., Guo, X., Yu, R., Xie, Z., & Zhang, L. (2021). DNN-MET: A deep neural networks method to integrate satellite-derived evapotranspiration products, eddy covariance observations and ancillary information. *Agricultural and Forest Meteorology, 308–309*, 108582. https://doi.org/10.1016/j.agrformet.2021.108582

[10] Shang, K., Yao, Y., Di, Z., Jia, K., Zhang, X., Fisher, J. B., Chen, J., Guo, X., Yang, J., Yu, R., Xie, Z., Liu, L., Ning, J., & Zhang, L. (2023). Coupling physical constraints with machine learning for satellite-derived evapotranspiration of the Tibetan Plateau. *Remote Sensing of Environment, 289*, 113519. https://doi.org/10.1016/j.rse.2023.113519

[11] Zhang, C., Brodylo, D., Rahman, M., Rahman, M. A., Douglas, T. A., & Comas, X. (2022). Using an object-based machine learning ensemble approach to upscale evapotranspiration measured from eddy covariance towers in a subtropical wetland. *Science of the Total Environment, 831*, 154969. https://doi.org/10.1016/j.scitotenv.2022.154969

[12] Zhang, Y., He, T., Liang, S., & Zhao, Z. (2023). A framework for estimating actual evapotranspiration through spatial heterogeneity-based machine learning approaches. *Agricultural Water Management, 289*, 108499. https://doi.org/10.1016/j.agwat.2023.108499

