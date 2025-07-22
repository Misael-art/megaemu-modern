import React from 'react';
import { View, Text, FlatList } from 'react-native';

const DATA = Array.from({ length: 1000 }, (_, i) => ({ id: i.toString(), title: `Item ${i}` }));

export default function HeavyList() {
  return (
    <View>
      <Text>Heavy List Component</Text>
      <FlatList
        data={DATA}
        renderItem={({ item }) => <Text>{item.title}</Text>}
        keyExtractor={item => item.id}
      />
    </View>
  );
}