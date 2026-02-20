/** App navigation: stack + bottom tabs. */

import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { NavigationContainer, createNavigationContainerRef } from '@react-navigation/native';
import { Text } from 'react-native';

import type { MainTabParamList, RootStackParamList } from '../types';
import { useAuth } from '../hooks/useAuth';
import { LoginScreen } from '../screens/LoginScreen';
import { InboxScreen } from '../screens/InboxScreen';
import { RulesScreen } from '../screens/RulesScreen';
import { SettingsScreen } from '../screens/SettingsScreen';
import { EmailDetailScreen } from '../screens/EmailDetailScreen';
import { ProposedEventScreen } from '../screens/ProposedEventScreen';

export const navigationRef = createNavigationContainerRef<RootStackParamList>();

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator<MainTabParamList>();

function TabIcon({ name, focused }: { name: string; focused: boolean }) {
  const icons: Record<string, string> = {
    Inbox: focused ? '[I]' : '[ ]',
    Rules: focused ? '[R]' : '[ ]',
    Settings: focused ? '[S]' : '[ ]',
  };
  return (
    <Text style={{ fontSize: 16, color: focused ? '#4A90D9' : '#999' }}>
      {icons[name] ?? '[ ]'}
    </Text>
  );
}

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ focused }) => (
          <TabIcon name={route.name} focused={focused} />
        ),
        tabBarActiveTintColor: '#4A90D9',
        tabBarInactiveTintColor: '#999',
        headerStyle: { backgroundColor: '#1a1a2e' },
        headerTintColor: '#fff',
      })}
    >
      <Tab.Screen
        name="Inbox"
        component={InboxScreen}
        options={{ title: 'EHA Inbox' }}
      />
      <Tab.Screen
        name="Rules"
        component={RulesScreen}
        options={{ title: 'Rules' }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{ title: 'Settings' }}
      />
    </Tab.Navigator>
  );
}

export function AppNavigator() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return null; // Or a splash screen
  }

  return (
    <NavigationContainer ref={navigationRef}>
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: '#1a1a2e' },
          headerTintColor: '#fff',
        }}
      >
        {!isAuthenticated ? (
          <Stack.Screen
            name="Login"
            component={LoginScreen}
            options={{ headerShown: false }}
          />
        ) : (
          <>
            <Stack.Screen
              name="Main"
              component={MainTabs}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="EmailDetail"
              component={EmailDetailScreen}
              options={{ title: 'Email' }}
            />
            <Stack.Screen
              name="ProposedEvent"
              component={ProposedEventScreen}
              options={{ title: 'Event Proposal' }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
