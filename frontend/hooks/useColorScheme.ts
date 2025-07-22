import { useState, useEffect } from 'react';
import { Appearance, ColorSchemeName } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

export function useColorScheme(): ColorSchemeName {
  const [colorScheme, setColorScheme] = useState(Appearance.getColorScheme());
  const [override, setOverride] = useState<string | null>(null);

  useEffect(() => {
    const loadOverride = async () => {
      const saved = await AsyncStorage.getItem('colorSchemeOverride');
      setOverride(saved);
    };
    loadOverride();
  }, []);

  useEffect(() => {
    const listener = Appearance.addChangeListener(({ colorScheme }) => {
      if (!override) {
        setColorScheme(colorScheme);
      }
    });
    return () => listener.remove();
  }, [override]);

  const toggleColorScheme = async () => {
    const newOverride = colorScheme === 'dark' ? 'light' : 'dark';
    await AsyncStorage.setItem('colorSchemeOverride', newOverride);
    setOverride(newOverride);
    setColorScheme(newOverride);
  };

  return override ? override as ColorSchemeName : colorScheme;
}

export { toggleColorScheme };