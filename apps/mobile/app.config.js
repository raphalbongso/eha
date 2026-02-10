export default {
  expo: {
    name: "EHA",
    slug: "eha",
    version: "1.0.0",
    orientation: "portrait",
    icon: "./assets/icon.png",
    userInterfaceStyle: "automatic",
    splash: {
      image: "./assets/splash.png",
      resizeMode: "contain",
      backgroundColor: "#1a1a2e",
    },
    assetBundlePatterns: ["**/*"],
    ios: {
      supportsTablet: true,
      bundleIdentifier: "com.eha.app",
      infoPlist: {
        NSCalendarsUsageDescription:
          "EHA needs calendar access to add events detected in your emails.",
        NSCalendarsFullAccessUsageDescription:
          "EHA needs calendar access to add events detected in your emails.",
      },
    },
    android: {
      adaptiveIcon: {
        foregroundImage: "./assets/adaptive-icon.png",
        backgroundColor: "#1a1a2e",
      },
      package: "com.eha.app",
      permissions: ["READ_CALENDAR", "WRITE_CALENDAR"],
    },
    plugins: ["expo-secure-store", "expo-notifications"],
    extra: {
      apiBaseUrl: process.env.API_BASE_URL || null,
    },
  },
};
