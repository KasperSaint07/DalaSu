# Literature review

## Scope and project decisions

DalaSu estimates daily evapotranspiration (ET) to support irrigation decisions for
small farms. The reviewed literature supports four choices in the project:

1. use FAO-56 Penman-Monteith reference evapotranspiration as an interpretable
   physical baseline;
2. train Random Forest and XGBoost models on meteorological variables and compare
   them with the baseline on the same held-out period;
3. retain Sentinel-2 vegetation information as a planned input for field-scale
   modelling; and
4. treat eddy-covariance ET as a useful but imperfect validation target because
   flux measurements have footprint, representativeness, and energy-balance
   limitations.

The twelve main sources below are peer-reviewed scientific articles. Two
foundational sources are included as reserves. Links and DOI metadata are recorded
for traceability; the list supplied for this review is preserved as the source set.

## Physical baseline and validation data

Allen et al. (1998) define the standardized FAO-56 Penman-Monteith method for
reference evapotranspiration. This supports the project's decision to implement
ET0 as a transparent physical baseline rather than presenting it as measured
actual crop ET. A crop coefficient or another crop-specific adjustment is needed
before ET0 can represent crop water use directly.

Foken (2008) reviews the energy-balance closure problem in eddy-covariance data
and attributes much of the residual to scale and landscape heterogeneity. This is
directly relevant to the AmeriFlux US-Ne2 target used by DalaSu: tower-derived
actual ET is appropriate for evaluation, but its uncertainty and spatial footprint
must be acknowledged when interpreting model errors.

Chen et al. (2021) combine eddy-covariance observations, process-model output,
meteorological forcing, and remote sensing in a deep-learning hybrid model. Their
use of temperature, precipitation, radiation, NDVI, and optional soil temperature
supports DalaSu's staged feature plan: begin with reproducible weather variables,
then evaluate the incremental value of Sentinel-2 vegetation information.

## Machine learning for evapotranspiration

Liu et al. (2021) compare KNN, Random Forest, SVM, XGBoost, ANN, and LSTM for
cropland ET using meteorological and remotely sensed factors. This comparative
design supports selecting Random Forest and XGBoost as practical tabular-data
models and evaluating both under one temporal split and one set of metrics.

Ferreira et al. (2022) study machine learning and multi-task learning for
estimating missing meteorological variables and reference ET across Brazil. The
results show that ML can remain useful when weather inputs are limited. For
DalaSu, this motivates retaining a compact feature set and later testing graceful
degradation when a weather provider omits humidity, radiation, or wind speed.

Jawad et al. (2025) combine a Penman-Monteith model with deep-neural-network
post-processing and compare the result with ECOSTRESS, MODIS, and OpenET. This
supports DalaSu's longer-term hybrid direction: keep the physical calculation
visible and use learning to correct systematic residuals rather than replacing
all physical structure at once.

ElGhawi et al. (2023) infer stomatal and aerodynamic resistances through a
physics-based and machine-learning hybrid. The study shows how physical
parameters can be learned while preserving an interpretable ET equation. DalaSu
can use this pattern in a later phase if a direct weather-only model performs well
but lacks transferability between crops or climates.

Koppa et al. (2022) embed a learned transpiration-stress formulation in a global
process-based evaporation model. Their results support hybrid modelling but also
show that data coverage affects generalization. For DalaSu, a model validated on
US-Ne2 should therefore be described as a proof of method, not as evidence of
accuracy for every farm in southern Kazakhstan.

## Remote sensing and spatial transfer

dos Santos et al. (2022) estimate actual-ET fraction from Sentinel-2 MSI features
with machine-learning algorithms and report strong results for boosted models.
This supports the planned use of Sentinel-2 NDVI and related vegetation features
in DalaSu, especially when thermal imagery is unavailable at the required spatial
or temporal resolution.

Rashid and Tian (2024) combine ECOSTRESS, Harmonized Landsat Sentinel-2 imagery,
reanalysis data, eddy-covariance observations, and neural-network
post-processing to estimate daily ET at 30 m. This supports a field-scale remote
sensing layer in DalaSu and highlights the need to validate on sites excluded
from training when assessing geographic transfer.

Shang et al. (2021) merge several satellite ET products with eddy-covariance
observations and ancillary information using a deep neural network. Their
validation under reduced training-site availability shows the value of combining
complementary inputs. DalaSu should therefore treat satellite data as additional
evidence rather than assume that one remote-sensing product is universally best.

Shang et al. (2023) add physical constraints to machine learning for
satellite-derived ET over the Tibetan Plateau. The constrained models are
especially useful under drought and sparse vegetation. This is relevant to
southern Kazakhstan and supports testing a hybrid model after the FAO-56 and
ML-only baselines have been established.

Zhang et al. (2022) use an object-based ensemble to upscale tower ET across a
subtropical wetland. The work demonstrates that tower observations require an
explicit spatial-upscaling strategy. DalaSu should avoid treating the value from
one flux-tower footprint as a pixel-perfect label for a heterogeneous field.

Zhang et al. (2023) account for spatial heterogeneity before fitting Random
Forest, gradient boosting, and Cubist models. Their framework performs better
than general models at site and basin scales. This supports adding spatially
stratified validation when DalaSu expands beyond one AmeriFlux station.

## Implications for DalaSu

The literature supports the current Phase 1 evaluation structure. FAO-56 ET0
provides an interpretable reference calculation, while Random Forest and XGBoost
provide strong tabular-data baselines. The models must use chronological
validation because the intended application predicts future irrigation demand;
randomly mixing dates would overstate operational performance. All candidates
should be evaluated on the same untouched test period with MAE, RMSE, bias, and a
correlation-based goodness-of-fit measure.

The reviewed work also supports the planned product sequence. Meteorological
features are sufficient for the first reproducible experiment. Sentinel-2
vegetation indices should be added only after the weather-only baseline is fixed,
so their contribution can be measured. A hybrid residual-correction or
physics-constrained model is a later experiment, not a substitute for the two
clear baselines. Finally, validation on US-Ne2 establishes technical feasibility;
deployment claims for Kazakhstan require local weather, crop, irrigation, and
field observations.

## Main references

1. Chen, J., Dafflon, B., Tran, A. P., Falco, N., and Hubbard, S. S. (2021).
   A deep learning hybrid predictive modeling approach for estimating
   evapotranspiration and ecosystem respiration. *Hydrology and Earth System
   Sciences*, 25(11), 6041-6066.
   [DOI](https://doi.org/10.5194/hess-25-6041-2021) ·
   [article](https://hess.copernicus.org/articles/25/6041/2021/)
2. dos Santos, R. A., Mantovani, E. C., Fernandes-Filho, E. I., Filgueiras, R.,
   Lourenço, R. D. S., Bufon, V. B., and Neale, C. M. U. (2022). Modeling
   actual evapotranspiration with MSI-Sentinel images and machine learning
   algorithms. *Atmosphere*, 13(9), 1518.
   [DOI](https://doi.org/10.3390/atmos13091518) ·
   [article](https://www.mdpi.com/2073-4433/13/9/1518)
3. ElGhawi, R., Kraft, B., Reimers, C., Reichstein, M., Körner, M., Gentine, P.,
   and Winkler, A. J. (2023). Hybrid modeling of evapotranspiration: Inferring
   stomatal and aerodynamic resistances using combined physics-based and machine
   learning. *Environmental Research Letters*, 18(3), 034039.
   [DOI](https://doi.org/10.1088/1748-9326/acbbe0) ·
   [article](https://iopscience.iop.org/article/10.1088/1748-9326/acbbe0/meta)
4. Ferreira, L. B., da Cunha, F. F., and Fernandes Filho, E. I. (2022).
   Exploring machine learning and multi-task learning to estimate meteorological
   data and reference evapotranspiration across Brazil. *Agricultural Water
   Management*, 259, 107281.
   [DOI](https://doi.org/10.1016/j.agwat.2021.107281) ·
   [author manuscript collection](https://locus.ufv.br/bitstreams/4cb76827-a54d-4452-b05f-552dffc48042/download)
5. Jawad, M., Behrangi, A., Farmani, M. A., Qiu, Y., Sohi, H. Y., Gupta, A., and
   Niu, G. Y. (2025). Improved evapotranspiration estimation using the
   Penman-Monteith equation with a deep learning model over the dry southwestern
   US: Comparison with ECOSTRESS, MODIS, and OpenET. *Journal of Hydrology*, 660,
   133460. [DOI](https://doi.org/10.1016/j.jhydrol.2025.133460) ·
   [manuscript record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5026281)
6. Koppa, A., Rains, D., Hulsman, P., Poyatos, R., and Miralles, D. G. (2022).
   A deep learning-based hybrid model of global terrestrial evaporation.
   *Nature Communications*, 13, 1912.
   [DOI](https://doi.org/10.1038/s41467-022-29543-7) ·
   [article](https://www.nature.com/articles/s41467-022-29543-7)
7. Liu, Y., Zhang, S., Zhang, J., Tang, L., and Bai, Y. (2021). Assessment and
   comparison of six machine learning models in estimating evapotranspiration
   over croplands using remote sensing and meteorological factors. *Remote
   Sensing*, 13(19), 3838. [DOI](https://doi.org/10.3390/rs13193838) ·
   [article](https://www.mdpi.com/2072-4292/13/19/3838)
8. Rashid, T., and Tian, D. (2024). Improved 30-m evapotranspiration estimates
   over 145 eddy covariance sites in the contiguous United States: The role of
   ECOSTRESS, Harmonized Landsat Sentinel-2 imagery, climate reanalysis, and deep
   neural network postprocessing. *Water Resources Research*, 60(4),
   e2023WR036313. [DOI](https://doi.org/10.1029/2023WR036313) ·
   [article](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2023WR036313)
9. Shang, K., Yao, Y., Liang, S., Zhang, Y., Fisher, J. B., Chen, J., Liu, S.,
   Xu, Z., Zhang, Y., Jia, K., Zhang, X., Yang, J., Bei, X., Guo, X., Yu, R.,
   Xie, Z., and Zhang, L. (2021). DNN-MET: A deep neural networks method to
   integrate satellite-derived evapotranspiration products, eddy covariance
   observations and ancillary information. *Agricultural and Forest
   Meteorology*, 308-309, 108582.
   [DOI](https://doi.org/10.1016/j.agrformet.2021.108582) ·
   [manuscript](https://srs.bnu.edu.cn/docs/20210830155547491007.pdf)
10. Shang, K., Yao, Y., Di, Z., Jia, K., Zhang, X., Fisher, J. B., Chen, J.,
    Guo, X., Yang, J., Yu, R., Xie, Z., Liu, L., Ning, J., and Zhang, L. (2023).
    Coupling physical constraints with machine learning for satellite-derived
    evapotranspiration of the Tibetan Plateau. *Remote Sensing of Environment*,
    289, 113519. [DOI](https://doi.org/10.1016/j.rse.2023.113519) ·
    [manuscript](https://ris.utwente.nl/ws/files/308074670/1_s2.0_S0034425723000706_main.pdf)
11. Zhang, C., Brodylo, D., Rahman, M., Rahman, M. A., Douglas, T. A., and
    Comas, X. (2022). Using an object-based machine learning ensemble approach
    to upscale evapotranspiration measured from eddy covariance towers in a
    subtropical wetland. *Science of the Total Environment*, 831, 154969.
    [DOI](https://doi.org/10.1016/j.scitotenv.2022.154969) ·
    [article](https://www.sciencedirect.com/science/article/abs/pii/S0048969722020629)
12. Zhang, Y., He, T., Liang, S., and Zhao, Z. (2023). A framework for
    estimating actual evapotranspiration through spatial heterogeneity-based
    machine learning approaches. *Agricultural Water Management*, 289, 108499.
    [DOI](https://doi.org/10.1016/j.agwat.2023.108499) ·
    [article](https://www.sciencedirect.com/science/article/pii/S0378377423003645)

## Reserve and foundational references

13. Foken, T. (2008). The energy balance closure problem: An overview.
    *Ecological Applications*, 18(6), 1351-1367.
    [DOI](https://doi.org/10.1890/06-0922.1)
14. Allen, R. G., Pereira, L. S., Raes, D., and Smith, M. (1998). *Crop
    Evapotranspiration: Guidelines for Computing Crop Water Requirements*. FAO
    Irrigation and Drainage Paper 56. Food and Agriculture Organization of the
    United Nations. [FAO publication](https://www.fao.org/4/X0490E/X0490E00.htm)
