/**
 * Tests for AlertCard component.
 */

import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';

import { AlertCard } from '../components/AlertCard';
import type { Alert } from '../types';

const baseAlert: Alert = {
  id: '1',
  message_id: 'msg_1',
  rule_id: 'rule_1',
  rule_name: 'Boss emails',
  read: false,
  created_at: '2024-02-01T12:00:00Z',
  subject: 'Urgent: review needed',
  from_addr: 'boss@company.com',
  snippet: 'Please review the attached document by EOD.',
};

describe('AlertCard', () => {
  it('renders subject and from address', () => {
    const onPress = jest.fn();
    const { getByText } = render(
      <AlertCard alert={baseAlert} onPress={onPress} />,
    );

    expect(getByText('boss@company.com')).toBeTruthy();
    expect(getByText('Urgent: review needed')).toBeTruthy();
  });

  it('renders snippet', () => {
    const onPress = jest.fn();
    const { getByText } = render(
      <AlertCard alert={baseAlert} onPress={onPress} />,
    );

    expect(getByText(/Please review/)).toBeTruthy();
  });

  it('renders rule tag when present', () => {
    const onPress = jest.fn();
    const { getByText } = render(
      <AlertCard alert={baseAlert} onPress={onPress} />,
    );

    expect(getByText('Boss emails')).toBeTruthy();
  });

  it('does not render rule tag when null', () => {
    const onPress = jest.fn();
    const alertNoRule = { ...baseAlert, rule_name: null };
    const { queryByText } = render(
      <AlertCard alert={alertNoRule} onPress={onPress} />,
    );

    expect(queryByText('Boss emails')).toBeNull();
  });

  it('handles null subject gracefully', () => {
    const onPress = jest.fn();
    const alertNoSubject = { ...baseAlert, subject: null };
    const { getByText } = render(
      <AlertCard alert={alertNoSubject} onPress={onPress} />,
    );

    expect(getByText('(no subject)')).toBeTruthy();
  });

  it('handles null from_addr gracefully', () => {
    const onPress = jest.fn();
    const alertNoFrom = { ...baseAlert, from_addr: null };
    const { getByText } = render(
      <AlertCard alert={alertNoFrom} onPress={onPress} />,
    );

    expect(getByText('Unknown sender')).toBeTruthy();
  });

  it('calls onPress when tapped', () => {
    const onPress = jest.fn();
    const { getByText } = render(
      <AlertCard alert={baseAlert} onPress={onPress} />,
    );

    fireEvent.press(getByText('Urgent: review needed'));
    expect(onPress).toHaveBeenCalledWith(baseAlert);
  });
});
