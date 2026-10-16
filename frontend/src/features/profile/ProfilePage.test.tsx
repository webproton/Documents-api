import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { Profile } from '@/api/profile'
import { api, apiError, server, testProfile } from '@/test/server'
import { renderApp, signInAs } from '@/test/utils'

/** Profile endpoint backed by a mutable object, like the real backend. */
function mockProfileApi(initial: Partial<Profile> = {}) {
  const profile: Profile = { ...testProfile, ...initial }
  const patches: unknown[] = []
  server.use(
    http.get(api('/profile/'), () => HttpResponse.json(profile)),
    http.patch(api('/profile/'), async ({ request }) => {
      const isMultipart = request.headers
        .get('Content-Type')
        ?.startsWith('multipart/form-data')
      if (isMultipart) {
        // request.formData() is broken under jsdom (File class mismatch),
        // so read the raw multipart body instead
        const body = await request.text()
        const name = /name="avatar"; filename="([^"]+)"/.exec(body)?.[1]
        patches.push({ avatar: name })
        profile.avatar = `https://bucket.s3.amazonaws.com/users/1/avatar/${name}`
      } else {
        const body = (await request.json()) as Record<string, string>
        patches.push(body)
        if (body.first_name) profile.first_name = body.first_name
        if (body.last_name) profile.last_name = body.last_name
        if (body.new_password) profile.has_password = true
      }
      const { first_name, last_name, avatar } = profile
      return HttpResponse.json({ first_name, last_name, avatar })
    }),
  )
  return { profile, patches }
}

async function openProfile(
  initial?: Partial<Profile>,
  userOptions?: Parameters<typeof renderApp>[1],
) {
  const mock = mockProfileApi(initial)
  signInAs()
  const app = renderApp('/profile', userOptions)
  await screen.findByRole('heading', { name: 'Personal information' })
  return { ...mock, ...app }
}

const imageFile = (name = 'me.png', type = 'image/png', size = 1024) =>
  new File([new Uint8Array(size)], name, { type })

describe('ProfilePage', () => {
  it('shows the current profile', async () => {
    await openProfile({ first_name: 'Jane', last_name: 'Doe' })

    expect(screen.getByLabelText('Email')).toHaveValue('user@example.com')
    expect(screen.getByLabelText('First name')).toHaveValue('Jane')
    expect(screen.getByLabelText('Last name')).toHaveValue('Doe')
    // Initials instead of a photo
    expect(screen.getByText('JD')).toBeInTheDocument()
  })

  it('shows the avatar photo when set', async () => {
    await openProfile({ avatar: 'https://bucket.s3.amazonaws.com/a.png' })

    expect(screen.getByAltText('Your avatar')).toHaveAttribute(
      'src',
      'https://bucket.s3.amazonaws.com/a.png',
    )
  })

  describe('personal information', () => {
    it('saves the name and refreshes the profile', async () => {
      const { patches, user } = await openProfile()
      const firstName = screen.getByLabelText('First name')

      await user.clear(firstName)
      await user.type(firstName, 'Ivan')
      await user.click(screen.getByRole('button', { name: 'Save changes' }))

      expect(await screen.findByText('Profile updated.')).toBeInTheDocument()
      expect(patches).toEqual([{ first_name: 'Ivan', last_name: 'User' }])
      expect(screen.getByLabelText('First name')).toHaveValue('Ivan')
      // Nothing left to save
      expect(
        screen.getByRole('button', { name: 'Save changes' }),
      ).toBeDisabled()
    })

    it('does not allow an empty name', async () => {
      const { patches, user } = await openProfile()

      await user.clear(screen.getByLabelText('Last name'))
      await user.click(screen.getByRole('button', { name: 'Save changes' }))

      expect(
        await screen.findByText('Last name cannot be empty'),
      ).toBeInTheDocument()
      expect(patches).toEqual([])
    })
  })

  describe('photo', () => {
    it('uploads a new avatar as multipart and shows it', async () => {
      const { patches, user } = await openProfile()

      await user.upload(screen.getByLabelText('Change photo'), imageFile())

      expect(await screen.findByText('Photo updated.')).toBeInTheDocument()
      expect(patches).toEqual([{ avatar: 'me.png' }])
      expect(await screen.findByAltText('Your avatar')).toHaveAttribute(
        'src',
        'https://bucket.s3.amazonaws.com/users/1/avatar/me.png',
      )
    })

    it('rejects files that are not JPEG or PNG before uploading', async () => {
      // The file dialog filters by `accept`, but "All files" can be chosen
      const { patches, user } = await openProfile({}, { applyAccept: false })

      await user.upload(
        screen.getByLabelText('Change photo'),
        imageFile('doc.gif', 'image/gif'),
      )

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Only JPEG and PNG are allowed',
      )
      expect(patches).toEqual([])
    })

    it('rejects files over 5 MB before uploading', async () => {
      const { patches, user } = await openProfile()

      await user.upload(
        screen.getByLabelText('Change photo'),
        imageFile('big.jpg', 'image/jpeg', 5 * 1024 * 1024 + 1),
      )

      expect(await screen.findByRole('alert')).toHaveTextContent('Max size 5MB')
      expect(patches).toEqual([])
    })
  })

  describe('password', () => {
    const passwordCard = () =>
      screen.getByRole('heading', { name: 'Change password' })
        .parentElement as HTMLElement

    async function fillPassword(
      user: Awaited<ReturnType<typeof openProfile>>['user'],
      {
        current = 'OldPass123',
        next = 'NewPass456',
        confirm = next,
      }: { current?: string; next?: string; confirm?: string } = {},
    ) {
      const card = within(passwordCard())
      await user.type(card.getByLabelText('Current password'), current)
      await user.type(card.getByLabelText('New password'), next)
      await user.type(card.getByLabelText('Confirm new password'), confirm)
      await user.click(card.getByRole('button', { name: 'Change password' }))
    }

    it('changes the password and clears the form', async () => {
      const { patches, user } = await openProfile()

      await fillPassword(user)

      expect(await screen.findByText('Password changed.')).toBeInTheDocument()
      // confirm_password is client-only
      expect(patches).toEqual([
        { current_password: 'OldPass123', new_password: 'NewPass456' },
      ])
      expect(screen.getByLabelText('Current password')).toHaveValue('')
    })

    it('shows a wrong current password under the field', async () => {
      mockProfileApi()
      server.use(
        http.patch(api('/profile/'), () =>
          apiError(400, {
            current_password: ['Current password is incorrect.'],
          }),
        ),
      )
      signInAs()
      const { user } = renderApp('/profile')
      await screen.findByRole('heading', { name: 'Change password' })

      await fillPassword(user)

      expect(
        await screen.findByText('Current password is incorrect.'),
      ).toBeInTheDocument()
      expect(screen.queryByText('Password changed.')).not.toBeInTheDocument()
    })

    it('checks that the new passwords match', async () => {
      const { patches, user } = await openProfile()

      await fillPassword(user, { confirm: 'Different999' })

      expect(
        await screen.findByText('Passwords do not match'),
      ).toBeInTheDocument()
      expect(patches).toEqual([])
    })
  })

  describe('set password (account created with Google)', () => {
    it('sets the first password without asking for a current one', async () => {
      const { patches, user } = await openProfile({ has_password: false })

      expect(screen.getByText(/You signed up with Google/)).toBeInTheDocument()
      expect(
        screen.queryByLabelText('Current password'),
      ).not.toBeInTheDocument()

      await user.type(screen.getByLabelText('New password'), 'NewPass456')
      await user.type(
        screen.getByLabelText('Confirm new password'),
        'NewPass456',
      )
      await user.click(screen.getByRole('button', { name: 'Set password' }))

      expect(await screen.findByText('Password set.')).toBeInTheDocument()
      expect(patches).toEqual([{ new_password: 'NewPass456' }])
      // Profile now has a password → the form switches to "change" mode
      expect(
        await screen.findByRole('heading', { name: 'Change password' }),
      ).toBeInTheDocument()
      expect(screen.getByLabelText('Current password')).toBeInTheDocument()
    })
  })
})
