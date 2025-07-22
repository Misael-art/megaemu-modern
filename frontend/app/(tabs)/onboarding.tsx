import React, { useState } from 'react';
import { View, Text, Button, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { useColorScheme } from '@/hooks/useColorScheme';
import AsyncStorage from '@react-native-async-storage/async-storage';

const Onboarding = () => {
  const colorScheme = useColorScheme();
  const router = useRouter();
  const [step, setStep] = useState(1);

  const nextStep = () => {
    if (step < 3) {
      setStep(step + 1);
    } else {
      AsyncStorage.setItem('onboarded', 'true');
      router.replace('(tabs)');
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: colorScheme === 'dark' ? '#000' : '#fff' }]}>
      {step === 1 && (
        <>
          <Text style={styles.title}>Bem-vindo ao MegaEmu Modern!</Text>
          <Text>Passo 1: Configure suas pastas de ROMs.</Text>
          <Button title="Próximo" onPress={nextStep} />
        </>
      )}
      {step === 2 && (
        <>
          <Text style={styles.title}>Tutorial Básico</Text>
          <Text>Passo 2: Aprenda a importar DAT files.</Text>
          <Button title="Próximo" onPress={nextStep} />
        </>
      )}
      {step === 3 && (
        <>
          <Text style={styles.title}>Pronto para começar!</Text>
          <Text>Passo 3: Explore o dashboard e funcionalidades.</Text>
          <Button title="Iniciar" onPress={nextStep} />
        </>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  title: { fontSize: 24, fontWeight: 'bold', marginBottom: 20 },
});

export default Onboarding;