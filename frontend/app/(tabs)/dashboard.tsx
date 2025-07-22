import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { LineChart, BarChart } from 'react-native-chart-kit';
import { useThemeColor } from '@/hooks/useThemeColor';
import ParallaxScrollView from '@/components/ParallaxScrollView';
import ThemedText from '@/components/ThemedText';
import { ThemedView } from '@/components/ThemedView';

import axios from 'axios';

const DashboardScreen = () => {
  const [stats, setStats] = useState({ totalRoms: 0, totalSystems: 0, romsBySystem: [] });
  const backgroundColor = useThemeColor({ light: '#fff', dark: '#151718' }, 'background');
  const textColor = useThemeColor({ light: '#000', dark: '#fff' }, 'text');

  const fetchStats = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/v1/roms/stats');
      setStats({
        totalRoms: response.data.total,
        totalSystems: response.data.systems?.length || 0,
        romsBySystem: response.data.systems?.map(s => ({ name: s.name, count: s.total_roms })) || []
      });
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const lineData = {
    labels: ['Total ROMs', 'Total Systems'],
    datasets: [{ data: [stats.totalRoms, stats.totalSystems] }]
  };

  const barData = {
    labels: stats.romsBySystem.map(s => s.name),
    datasets: [{ data: stats.romsBySystem.map(s => s.count) }]
  };

  return (
    <ParallaxScrollView
      headerBackgroundColor={{ light: '#A1CEDC', dark: '#1D3D47' }}
      headerImage={
        <ThemedText type="title" style={styles.headerText}>Dashboard de Estatísticas</ThemedText>
      }>
      <ThemedView style={styles.container}>
        <ThemedText type="subtitle">Estatísticas em Tempo Real</ThemedText>
        <LineChart
          data={lineData}
          width={300}
          height={220}
          chartConfig={{ backgroundColor, color: () => textColor }}
        />
        <BarChart
          data={barData}
          width={300}
          height={220}
          chartConfig={{ backgroundColor, color: () => textColor }}
        />
      </ThemedView>
    </ParallaxScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  headerText: { color: '#fff', fontSize: 24, textAlign: 'center', marginTop: 20 }
});

export default DashboardScreen;