import React, { useState, useEffect } from 'react';
import { View, Text } from 'react-native';
import * as Progress from 'react-native-progress';
import { ThemedView } from '@/components/ThemedView';
import { ThemedText } from '@/components/ThemedText';

export default function ProgressExample() {
  const [progress, setProgress] = useState(0);
  const [eta, setEta] = useState(0);

  useEffect(() => {
    const totalTime = 60; // Tempo total simulado em segundos
    const interval = setInterval(() => {
      setProgress((prev) => {
        const newProgress = prev + 0.01;
        if (newProgress >= 1) {
          clearInterval(interval);
          return 1;
        }
        const timeElapsed = newProgress * totalTime;
        const remainingTime = totalTime - timeElapsed;
        setEta(remainingTime);
        return newProgress;
      });
    }, 600); // Atualiza a cada 0.6 segundos

    return () => clearInterval(interval);
  }, []);

  return (
    <ThemedView style={{ alignItems: 'center', padding: 20 }}>
      <ThemedText type="subtitle">Progress Bar with ETA</ThemedText>
      <Progress.Bar progress={progress} width={200} />
      <ThemedText>Progress: {(progress * 100).toFixed(0)}%</ThemedText>
      <ThemedText>ETA: {eta.toFixed(0)} seconds</ThemedText>
    </ThemedView>
  );
}