import React, { useState } from 'react';
import { View, TextInput, Button, Text } from 'react-native';
import axios from 'axios';

export default function RegisterScreen({ navigation }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const submit = async () => {
    try {
      const res = await axios.post('http://localhost:8000/auth/register', { username, password });
      setError('');
      navigation.navigate('Login');
    } catch (e) {
      setError('Falha ao registrar');
    }
  };

  return (
    <View style={{ flex:1, padding:16 }}>
      <Text>Registrar</Text>
      <TextInput placeholder="username" value={username} onChangeText={setUsername} />
      <TextInput placeholder="password" secureTextEntry value={password} onChangeText={setPassword} />
      <Button title="Registrar" onPress={submit} />
      {error ? <Text style={{ color:'red' }}>{error}</Text> : null}
    </View>
  );
}
