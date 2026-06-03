import React, { useState } from 'react';
import { View, TextInput, Button, Text } from 'react-native';
import axios from 'axios';

export default function LoginScreen({ navigation }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const submit = async () => {
    try {
      const res = await axios.post('http://localhost:8000/auth/login', { username, password });
      const token = res.data.access_token || res.data.token;
      // armazenar token localmente (AsyncStorage) — simplificado aqui
      console.log('token', token);
      setError('');
      navigation.navigate('Home');
    } catch (e) {
      setError('Falha ao logar');
    }
  };

  return (
    <View style={{ flex:1, padding:16 }}>
      <Text>Login</Text>
      <TextInput placeholder="username" value={username} onChangeText={setUsername} />
      <TextInput placeholder="password" secureTextEntry value={password} onChangeText={setPassword} />
      <Button title="Entrar" onPress={submit} />
      <Button title="Registrar" onPress={() => navigation.navigate('Register')} />
      {error ? <Text style={{ color:'red' }}>{error}</Text> : null}
    </View>
  );
}
