import React, { useEffect, useState } from 'react';
import { View, Text, Button } from 'react-native';
import axios from 'axios';

export default function HomeScreen({ navigation }) {
  const [status, setStatus] = useState('loading');

  useEffect(() => {
    axios.get('http://localhost:8000/health')
      .then(res => setStatus(res.data.status))
      .catch(() => setStatus('offline'));
  }, []);

  return (
    <View style={{ flex:1, alignItems:'center', justifyContent:'center' }}>
      <Text>Backend status: {status}</Text>
      <Button title="Ver Vocabulário" onPress={() => navigation.navigate('Vocab')} />
    </View>
  );
}
