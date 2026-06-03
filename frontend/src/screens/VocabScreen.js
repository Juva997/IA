import React, { useEffect, useState } from 'react';
import { View, Text, FlatList } from 'react-native';
import axios from 'axios';

export default function VocabScreen() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    axios.get('http://localhost:8000/vocab/')
      .then(res => setItems(res.data))
      .catch(() => setItems([]));
  }, []);

  return (
    <View style={{ flex:1, padding:16 }}>
      <Text style={{ fontSize:18, marginBottom:8 }}>Vocabulário</Text>
      <FlatList
        data={items}
        keyExtractor={(item) => String(item.id)}
        renderItem={({item}) => (
          <View style={{ paddingVertical:8 }}>
            <Text style={{ fontWeight:'bold' }}>{item.word}</Text>
            <Text>{item.translation} — {item.language}</Text>
          </View>
        )}
      />
    </View>
  );
}
