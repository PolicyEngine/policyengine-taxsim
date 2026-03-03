/**
 * Load the pre-extracted configuration data
 * This data is generated at build time from the original YAML file
 */
export const loadConfigurationData = async () => {
  try {
    const { assetUrl } = await import('./basePath');
    const response = await fetch(assetUrl('/config-data.json'));
    if (!response.ok) {
      throw new Error(`Failed to load configuration data: ${response.status}`);
    }
    const configData = await response.json();
    return configData;
  } catch (error) {
    console.error('Error loading configuration data:', error);
    throw error;
  }
};
