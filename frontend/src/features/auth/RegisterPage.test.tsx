import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { api, apiError, server } from '@/test/server'
import { renderApp } from '@/test/utils'

async function fillForm(
  user: ReturnType<typeof renderApp>['user'],
  {
    password = 'StrongPass123',
    confirm = password,
  }: { password?: string; confirm?: string } = {},
) {
  await user.type(await screen.findByLabelText('Email'), 'new@example.com')
  await user.type(screen.getByLabelText('Password'), password)
  await user.type(screen.getByLabelText('Confirm password'), confirm)
  await user.click(screen.getByRole('button', { name: 'Create account' }))
}

describe('RegisterPage', () => {
  it('sends email and password and asks to check the inbox', async () => {
    let body: unknown
    server.use(
      http.post(api('/auth/register/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(
          { message: 'User created. Please confirm email.' },
          { status: 201 },
        )
      }),
    )
    const { user } = renderApp('/register')

    await fillForm(user)

    expect(
      await screen.findByRole('heading', { name: 'Check your email' }),
    ).toBeInTheDocument()
    expect(screen.getByText('new@example.com')).toBeInTheDocument()
    // confirmPassword is a client-only field
    expect(body).toEqual({
      email: 'new@example.com',
      password: 'StrongPass123',
    })
  })

  it('shows server validation errors under the fields', async () => {
    server.use(
      http.post(api('/auth/register/'), () =>
        apiError(400, {
          email: ['Email already exists'],
          password: ['This password is too common.'],
        }),
      ),
    )
    const { user } = renderApp('/register')

    await fillForm(user)

    expect(await screen.findByText('Email already exists')).toBeInTheDocument()
    expect(screen.getByText('This password is too common.')).toBeInTheDocument()
    // Field messages are not duplicated in the form-level alert
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows non-field errors in the form alert', async () => {
    server.use(
      http.post(api('/auth/register/'), () =>
        apiError(400, { non_field_errors: ['Password too similar to email'] }),
      ),
    )
    const { user } = renderApp('/register')

    await fillForm(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Password too similar to email',
    )
  })

  it('checks that passwords match', async () => {
    const { user } = renderApp('/register')

    await fillForm(user, { confirm: 'Different123' })

    expect(
      await screen.findByText('Passwords do not match'),
    ).toBeInTheDocument()
  })
})
