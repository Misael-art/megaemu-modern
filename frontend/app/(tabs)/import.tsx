import React, { useState } from 'react';
import { Button, FlatList, TextInput } from 'react-native';
import { ThemedText } from '@/components/ThemedText';
import { ThemedView } from '@/components/ThemedView';
import ParallaxScrollView from '@/components/ParallaxScrollView';
import * as Progress from 'react-native-progress';
import { useUndoRedo } from '@/hooks/useUndoRedo';

export default function ImportScreen() {
  const [sourcePath, setSourcePath] = useState('');
  const [taskId, setTaskId] = useState(null);
  const [progress, setProgress] = useState(0);
  const { state: previews, set: setPreviews, undo, redo } = useUndoRedo([]);
  const [intervalId, setIntervalId] = useState(null);

  const startImport = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/roms/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_path: sourcePath, recursive: true }),
      });
      const data = await response.json();
      setTaskId(data.task_id);
      const id = setInterval(() => pollProgress(data.task_id), 1000);
      setIntervalId(id);
    } catch (error) {
      console.error('Error starting import:', error);
    }
  };

  const pollProgress = async (id) => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/tasks/${id}`);
      const data = await response.json();
      setProgress(data.progress / 100);
      setPreviews(data.status_message ? data.status_message.split('\n') : []);
      if (data.status === 'completed') {
        clearInterval(intervalId);
        setIntervalId(null);
      }
    } catch (error) {
      console.error('Error polling progress:', error);
    }
  };

  return (
    <ParallaxScrollView
      headerBackgroundColor={{ light: '#A1CEDC', dark: '#1D3D47' }}
      headerImage={<ThemedText>Import ROMs</ThemedText>}>
      <ThemedView>
        <ThemedText>Enter source path:</ThemedText>
        <TextInput
          style={{ borderWidth: 1, padding: 8, margin: 8 }}
          value={sourcePath}
          onChangeText={setSourcePath}
        />
        <Button title="Start Import" onPress={startImport} />
        <Button title="Undo" onPress={undo} disabled={previews.length === 0} />
        <Button title="Redo" onPress={redo} />
        {taskId && (
          <>
            <Progress.Bar progress={progress} width={200} />
            <FlatList
              data={previews}
              renderItem={({ item }) => <ThemedText>{item}</ThemedText>}
              keyExtractor={(item, index) => index.toString()}
            />
          </>
        )}
      </ThemedView>
    </ParallaxScrollView>
  );
}