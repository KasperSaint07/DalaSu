# ADR 0003: Use Flutter for the mobile application

**Status:** Accepted (technology choice; implementation pending)  
**Date:** 2026-10-22

## Context

DalaSu needs a farmer-facing client for entering field data and displaying planned recommendations. The team has two developers, and a shared mobile codebase limits duplicated UI work while retaining a path to Android and iOS. Kazakh/Russian localization and seasonal charts are desirable features (FR-12–FR-13), not completed functionality. Initial supported platforms and OS versions remain to be defined.

## Alternatives considered

| Option | Benefits | Tradeoffs |
|---|---|---|
| Flutter | Shared Dart application and widget code; documented localization workflow. | Dart/tooling required; platform plugins and builds need verification. |
| React Native | Shared React/JavaScript or TypeScript application using native components. | Still requires library selection and platform testing; no decisive team React advantage is established. |
| Separate native apps | Kotlin/Jetpack Compose for Android and Swift/SwiftUI for iOS provide direct platform integration. | Separate UI implementations increase development and maintenance scope. |

## Decision

Use **Flutter** for the mobile client, as confirmed by the project owner on 2026-10-22. Connect to the FastAPI backend through HTTPS/JSON; keep scientific calculations and inference on the backend initially.

This is a project-fit choice, not a measured claim of better performance than React Native. Supporting both mobile platforms does not imply simultaneous public releases.

## Consequences

- Share most application UI and client logic, while testing each supported platform separately.
- Verify mapping/chart packages, build requirements, and any notification integration before relying on them.
- Implement and verify Kazakh/Russian coverage if FR-13 enters delivery scope; the framework does not supply project translations automatically.
- Offline caching is a possible enhancement, not an existing requirement or implemented feature. If added, show recommendation timestamps and stale-data states and define synchronization behavior.
- Do not imply that cached recommendations contain fresh weather or that selecting Flutter provides offline inference.
- Verify the field-entry and recommendation-display flow against the real API on supported devices before claiming completion.

## Revisit when

Reconsider if a critical platform integration is unsupported, actual maintenance effort becomes unacceptable, or delivery requirements change to a single native platform.

## References

- [Technology comparison: mobile](../05-technology-comparison.md#5-mobile-application-framework).
- [Flutter platform integration](https://docs.flutter.dev/platform-integration).
- [Flutter internationalization](https://docs.flutter.dev/ui/internationalization).
- [Flutter offline-first support](https://docs.flutter.dev/app-architecture/design-patterns/offline-first).
- [React Native components](https://reactnative.dev/docs/intro-react-native-components).
- [Android Jetpack Compose](https://developer.android.com/compose).
- [Apple SwiftUI](https://developer.apple.com/swiftui/).
